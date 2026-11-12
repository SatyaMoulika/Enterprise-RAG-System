from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.config import settings
from database.session import get_db
from dependencies.auth import get_current_user, require_admin
from models.user import User
from schemas.document import DocumentLimits, DocumentResponse
from services.document_service import DocumentService

document_router = APIRouter(prefix="/documents", tags=["Documents"])


@document_router.post("/upload", response_model=DocumentResponse, status_code=201)
def upload_document(
    file: UploadFile, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
):
    return DocumentService.upload_document(
        db=db, file=file, enterprise_id=current_user.enterprise_id
    )


@document_router.get("/limits", response_model=DocumentLimits)
def upload_limits(current_user: User = Depends(get_current_user)):
    return {"allowed_extensions": [".pdf", ".txt"], "max_upload_bytes": settings.MAX_UPLOAD_BYTES}


@document_router.get("/list", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return DocumentService.get_documents(db=db, enterprise_id=current_user.enterprise_id)


@document_router.delete("/{document_id}")
def delete_document(
    document_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
):
    if not DocumentService.delete_document(db, document_id, current_user.enterprise_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}
