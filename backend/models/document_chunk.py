from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime
from sqlalchemy.sql import func

from database.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(Integer, ForeignKey("documents.id"), index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), index=True)

    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())