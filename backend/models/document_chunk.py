from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.sql import func

from database.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(Integer, ForeignKey("documents.id"), index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), index=True)

    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer)
    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)
    section = Column(Text, nullable=True)
    start_offset = Column(Integer, nullable=True)
    end_offset = Column(Integer, nullable=True)
    section_key = Column(Text, nullable=True)

    embedding = Column(JSON, nullable=True)
    embedding_model = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
