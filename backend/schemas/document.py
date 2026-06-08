from datetime import datetime
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    title: str
    file_path: str
    enterprise_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DeleteDocumentResponse(BaseModel):
    message: str