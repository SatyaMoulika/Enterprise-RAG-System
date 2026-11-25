# models/document.py

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), index=True)
    title = Column(String(255), nullable=False)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    content_hash = Column(String(64), nullable=True, index=True)
    pending_file_path = Column(Text, nullable=True)
    pending_content_hash = Column(String(64), nullable=True)
    extraction_warnings = Column(JSON, nullable=False, default=list, server_default="[]")
    index_metadata = Column(JSON, nullable=False, default=dict, server_default="{}")
    index_status = Column(String(20), nullable=False, default="ready", server_default="ready")
    index_error = Column(Text, nullable=True)
    index_started_at = Column(DateTime(timezone=True), nullable=True)

    visibility = Column(String(20), nullable=False, default="company", server_default="company")
    grants = relationship("DocumentGrant", cascade="all, delete-orphan", lazy="selectin")

    @property
    def recipient_ids(self):
        return [grant.user_id for grant in self.grants]


class DocumentGrant(Base):
    __tablename__ = "document_grants"
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
