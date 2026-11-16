from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from core.config import settings
from database.session import get_db
from dependencies.auth import get_current_user, require_admin
from models.document import Document
from models.user import User
from schemas.document import DocumentAccess, DocumentLimits, DocumentResponse
from services.document_access import accessible_documents, validate_access
from services.document_service import DocumentService

document_router = APIRouter(prefix="/documents", tags=["Documents"])


@document_router.post("/upload", response_model=DocumentResponse, status_code=201)
def upload_document(
    file: UploadFile,
    access: str = Form('{"visibility":"company"}'),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        permissions = DocumentAccess.model_validate_json(access)
    except ValidationError:
        raise HTTPException(422, "Invalid document access settings") from None
    return DocumentService.upload_document(
        db=db, file=file, enterprise_id=current_user.enterprise_id, access=permissions
    )


@document_router.get("/limits", response_model=DocumentLimits)
def upload_limits(current_user: User = Depends(get_current_user)):
    return {"allowed_extensions": [".pdf", ".txt"], "max_upload_bytes": settings.MAX_UPLOAD_BYTES}


@document_router.get("/list", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Document)
        .filter(
            Document.enterprise_id == current_user.enterprise_id, accessible_documents(current_user)
        )
        .order_by(Document.created_at.desc())
        .all()
    )


@document_router.delete("/{document_id}")
def delete_document(
    document_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
):
    if not DocumentService.delete_document(db, document_id, current_user.enterprise_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}


@document_router.patch("/{document_id}/access", response_model=DocumentResponse)
def change_access(
    document_id: int,
    payload: DocumentAccess,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.enterprise_id == current_user.enterprise_id)
        .first()
    )
    if document is None:
        raise HTTPException(404, "Document not found")
    grants = validate_access(db, current_user.enterprise_id, payload)
    document.visibility = payload.visibility
    document.grants = grants
    db.commit()
    db.refresh(document)
    return document


@document_router.get("/{document_id}/file")
def get_file(
    document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.enterprise_id == current_user.enterprise_id,
            accessible_documents(current_user),
        )
        .first()
    )
    if document is None:
        raise HTTPException(404, "Document not found")
    path = Path(document.file_path).resolve()
    base = (settings.UPLOAD_DIR / f"enterprise_{current_user.enterprise_id}").resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise HTTPException(404, "Document file unavailable")
    return FileResponse(
        path,
        filename=document.title,
        media_type="application/pdf" if path.suffix.lower() == ".pdf" else "text/plain",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
