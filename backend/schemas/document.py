from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    enterprise_id: int
    created_at: datetime


class DeleteDocumentResponse(BaseModel):
    message: str


class DocumentLimits(BaseModel):
    allowed_extensions: list[str]
    max_upload_bytes: int
