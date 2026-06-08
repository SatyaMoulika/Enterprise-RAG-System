from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from database.session import get_db
from dependencies.auth import get_current_user
from models.user import User
from schemas.document import DocumentResponse
from services.document_service import DocumentService

document_router = APIRouter(prefix="/documents", tags=["Documents"])

@document_router.post("/upload")
def upload_document(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return DocumentService.upload_document(
        db=db,
        file=file,
        enterprise_id=current_user.enterprise_id
    )


@document_router.get("/list", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return DocumentService.get_documents(
        db=db,
        enterprise_id=current_user.enterprise_id
    )

@document_router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    deleted = DocumentService.delete_document(
        db=db,
        document_id=document_id,
        enterprise_id=current_user.enterprise_id
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    return {
        "message":
        "Document deleted successfully"
    }