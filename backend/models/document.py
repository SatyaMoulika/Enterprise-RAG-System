# models/document.py

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
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

    visibility = Column(String(20), nullable=False, default="company", server_default="company")
    grants = relationship("DocumentGrant", cascade="all, delete-orphan", lazy="selectin")

    @property
    def recipient_ids(self):
        return [grant.user_id for grant in self.grants]


class DocumentGrant(Base):
    __tablename__ = "document_grants"
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
