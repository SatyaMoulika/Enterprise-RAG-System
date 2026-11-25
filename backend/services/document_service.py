from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select, update

from core.config import settings
from core.errors import InvalidDocument, UploadTooLarge
from models.document import Document
from models.document_chunk import DocumentChunk
from repositories.document_repository import DocumentRepository
from services.indexing_service import prepare_index


class DocumentService:
    @staticmethod
    def upload_document(db, enterprise_id: int, file, access=None, background=False):
        from schemas.document import DocumentAccess
        from services.document_access import validate_access

        access = access or DocumentAccess()
        grants = validate_access(db, enterprise_id, access)
        filename = file.filename or ""
        # Reject path components on every OS, including Windows-style separators.
        if (
            "\\" in filename
            or PurePosixPath(filename).name != filename
            or "\x00" in filename
            or len(filename) > 255
        ):
            raise InvalidDocument("Use a plain filename without path components")
        suffix = Path(filename).suffix.lower()
        if suffix not in {".txt", ".pdf"}:
            raise InvalidDocument("Only .txt and .pdf files are supported")
        directory = settings.UPLOAD_DIR / f"enterprise_{enterprise_id}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid4().hex}{suffix}"
        try:
            total = 0
            digest = sha256()
            with path.open("xb") as output:
                while block := file.file.read(64 * 1024):
                    total += len(block)
                    if total > settings.MAX_UPLOAD_BYTES:
                        raise UploadTooLarge("Document exceeds the upload limit")
                    output.write(block)
                    digest.update(block)
            if not total:
                raise InvalidDocument("Document is empty")
            # Reuse identical uploads only when filename AND access grants agree.
            # A duplicate must never broaden another document's visibility.
            existing = db.scalars(
                select(Document).where(
                    Document.enterprise_id == enterprise_id,
                    Document.content_hash == digest.hexdigest(),
                    Document.title == filename,
                )
            ).all()
            for previous in existing:
                if previous.visibility == access.visibility and sorted(
                    previous.recipient_ids
                ) == sorted(set(access.recipient_ids)):
                    path.unlink(missing_ok=True)
                    return previous
            indexed, warnings, metadata = ([], [], {}) if background else prepare_index(path)
            document = Document(
                enterprise_id=enterprise_id,
                title=filename,
                file_path=str(path),
                visibility=access.visibility,
                grants=grants,
                content_hash=digest.hexdigest(),
                extraction_warnings=warnings,
                index_metadata=metadata,
                index_status="queued" if background else "ready",
            )
            db.add(document)
            db.flush()
            for chunk in indexed:
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        enterprise_id=enterprise_id,
                        **chunk,
                    )
                )
            # Documents, chunks and embeddings commit together, avoiding stale external indexes.
            db.commit()
        except Exception:
            db.rollback()
            path.unlink(missing_ok=True)
            raise
        db.refresh(document)
        return document

    @staticmethod
    def queue_reindex(db, enterprise_id, document_id):
        document = db.scalar(
            select(Document)
            .where(Document.enterprise_id == enterprise_id, Document.id == document_id)
            .with_for_update()
        )
        if document is None:
            return None
        if document.index_status != "indexing":
            document.index_status = "queued"
            document.index_error = None
            db.commit()
            db.refresh(document)
        return document

    @staticmethod
    def process_next(db, document_id=None):
        """CAS claim supports multiple workers. Existing chunks survive failed rebuilds."""
        identity = db.scalar(
            select(Document.id)
            .where(
                Document.index_status == "queued",
                Document.id == document_id if document_id else True,
            )
            .order_by(Document.id)
            .limit(1)
        )
        if identity is None:
            return False
        claimed = db.execute(
            update(Document)
            .where(Document.id == identity, Document.index_status == "queued")
            .values(index_status="indexing", index_started_at=datetime.now(UTC))
        )
        db.commit()
        if not claimed.rowcount:
            return True
        try:
            document = db.get(Document, identity)
            path = Path(document.pending_file_path or document.file_path).resolve()
            base = (settings.UPLOAD_DIR / f"enterprise_{document.enterprise_id}").resolve()
            if not path.is_relative_to(base):
                raise InvalidDocument("Stored source is outside the workspace upload directory")
            indexed, warnings, metadata = prepare_index(path)
            # Recheck after provider calls: deletion must never resurrect a document.
            db.expire_all()
            document = db.scalar(select(Document).where(Document.id == identity).with_for_update())
            if document is None:
                return True
            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == identity))
            for chunk in indexed:
                db.add(
                    DocumentChunk(
                        document_id=identity, enterprise_id=document.enterprise_id, **chunk
                    )
                )
            document.extraction_warnings = warnings
            document.index_metadata = metadata
            document.content_hash = sha256(path.read_bytes()).hexdigest()
            document.index_status = "ready"
            document.index_error = None
            document.index_started_at = None
            old_path = Path(document.file_path)
            document.file_path = str(path)
            document.pending_file_path = None
            document.pending_content_hash = None
            db.commit()
            if old_path.resolve() != path and old_path.resolve().is_relative_to(base):
                try:
                    old_path.unlink(missing_ok=True)
                except OSError:
                    pass
        except Exception as exc:
            db.rollback()
            # Persist a safe error, never provider URLs, filenames or extracted private text.
            db.execute(
                update(Document)
                .where(Document.id == identity)
                .values(
                    index_status="failed",
                    index_started_at=None,
                    index_error=str(exc)
                    if isinstance(exc, InvalidDocument)
                    else "Indexing failed. Check the provider and retry indexing.",
                )
            )
            db.commit()
        return True

    @staticmethod
    def replace_source(db, enterprise_id, document_id, file):
        document = db.scalar(
            select(Document)
            .where(Document.id == document_id, Document.enterprise_id == enterprise_id)
            .with_for_update()
        )
        if document is None:
            return None
        if document.index_status == "indexing":
            raise HTTPException(
                409, "Wait for current indexing to finish before replacing the source"
            )
        # Keep the document identity, grants and active file/index until the worker commits.
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".txt", ".pdf"}:
            raise InvalidDocument("Only .txt and .pdf files are supported")
        directory = settings.UPLOAD_DIR / f"enterprise_{enterprise_id}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid4().hex}{suffix}"
        previous_pending = document.pending_file_path
        try:
            digest, total = sha256(), 0
            with path.open("xb") as output:
                while block := file.file.read(64 * 1024):
                    total += len(block)
                    if total > settings.MAX_UPLOAD_BYTES:
                        raise UploadTooLarge("Document exceeds the upload limit")
                    digest.update(block)
                    output.write(block)
            if not total:
                raise InvalidDocument("Document is empty")
            document.pending_file_path = str(path)
            document.pending_content_hash = digest.hexdigest()
            document.index_status = "queued"
            document.index_error = None
            db.commit()
        except Exception:
            db.rollback()
            path.unlink(missing_ok=True)
            raise
        if previous_pending and Path(previous_pending).resolve().is_relative_to(
            directory.resolve()
        ):
            Path(previous_pending).unlink(missing_ok=True)
        db.refresh(document)
        return document

    @classmethod
    def get_documents(cls, db, enterprise_id: int):
        return DocumentRepository.get_by_enterprise(db=db, enterprise_id=enterprise_id)

    @classmethod
    def delete_document(cls, db, document_id, enterprise_id):
        document = (
            db.query(Document)
            .filter(Document.id == document_id, Document.enterprise_id == enterprise_id)
            .first()
        )
        if document is None:
            return False
        stored_path = Path(document.file_path)
        pending_path = Path(document.pending_file_path) if document.pending_file_path else None
        db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.enterprise_id == enterprise_id,
            )
        )
        db.delete(document)
        db.commit()
        # Database deletion takes effect before file cleanup. Never unlink arbitrary legacy paths.
        base = (settings.UPLOAD_DIR / f"enterprise_{enterprise_id}").resolve()
        try:
            if stored_path.resolve().is_relative_to(base):
                stored_path.unlink(missing_ok=True)
            if pending_path and pending_path.resolve().is_relative_to(base):
                pending_path.unlink(missing_ok=True)
        except OSError:
            # A leftover file is not retrievable; operators can clean it up later.
            pass
        return True
