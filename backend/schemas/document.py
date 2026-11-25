from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    enterprise_id: int
    created_at: datetime
    visibility: Literal["company", "personal", "restricted"]
    recipient_ids: list[int] = Field(default_factory=list)
    index_status: str = "ready"
    index_error: str | None = None
    extraction_warnings: list[str] = Field(default_factory=list)
    index_metadata: dict = Field(default_factory=dict)


class DeleteDocumentResponse(BaseModel):
    message: str


class DocumentLimits(BaseModel):
    allowed_extensions: list[str]
    max_upload_bytes: int


class DocumentAccess(BaseModel):
    visibility: Literal["company", "personal", "restricted"] = "company"
    recipient_ids: list[int] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def valid_recipients(self):
        count = len(set(self.recipient_ids))
        if (
            (self.visibility == "company" and count)
            or (self.visibility == "personal" and count != 1)
            or (self.visibility == "restricted" and not count)
        ):
            raise ValueError(
                "Company documents have no recipients; personal needs one; restricted needs at least one"
            )
        return self
