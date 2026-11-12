from pathlib import Path, PurePosixPath
from uuid import uuid4

from sqlalchemy import delete

from core.config import settings
from core.errors import InvalidDocument, UploadTooLarge
from models.document import Document
from models.document_chunk import DocumentChunk
from repositories.document_repository import DocumentRepository
from services.chunking_service import ChunkingService
from services.embedding_service import EmbeddingService
from services.loader_service import LoaderService


class DocumentService:
    @staticmethod
    def upload_document(db, enterprise_id: int, file):
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
            with path.open("xb") as output:
                while block := file.file.read(64 * 1024):
                    total += len(block)
                    if total > settings.MAX_UPLOAD_BYTES:
                        raise UploadTooLarge("Document exceeds the upload limit")
                    output.write(block)
            text = LoaderService.extract_text(path)
            chunks = ChunkingService.chunk_text(text)
            vectors = EmbeddingService.embed_texts(chunks)
            document = Document(enterprise_id=enterprise_id, title=filename, file_path=str(path))
            db.add(document)
            db.flush()
            for number, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        enterprise_id=enterprise_id,
                        chunk_text=chunk,
                        chunk_index=number,
                        embedding=vector,
                        embedding_model=f"{settings.EMBEDDING_BACKEND}:{settings.EMBEDDING_MODEL}",
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
        except OSError:
            # A leftover file is not retrievable; operators can clean it up later.
            pass
        return True
