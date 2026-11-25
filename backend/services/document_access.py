"""One access predicate for listing, file delivery and retrieval."""

from fastapi import HTTPException
from sqlalchemy import or_, select, true

from models.document import Document, DocumentGrant
from models.user import User


def accessible_documents(user=None):
    if user is not None and user.role == "admin":
        return true()
    return or_(
        Document.visibility == "company",
        Document.id.in_(
            # Grants reference account IDs, never email addresses.
            select(DocumentGrant.document_id).where(
                DocumentGrant.user_id == (user.id if user else -1)
            )
        ),
    )


def require_document_read_access(db, document_id, enterprise_id, user=None):
    """Validate explicit file selection without revealing another user's documents."""
    unavailable = HTTPException(
        404,
        "Document not found or access is unavailable. Choose an available file in My documents.",
    )
    if user is not None and (not user.is_active or user.enterprise_id != enterprise_id):
        raise unavailable
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.enterprise_id == enterprise_id,
            accessible_documents(user),
        )
    )
    if document is None:
        raise unavailable
    return document


def validate_access(db, enterprise_id, access):
    ids = set(access.recipient_ids)
    users = (
        db.query(User)
        .filter(User.id.in_(ids), User.enterprise_id == enterprise_id, User.is_active.is_(True))
        .all()
    )
    if len(users) != len(ids):
        raise HTTPException(422, "Select active employees in this workspace")
    return [DocumentGrant(user_id=i) for i in sorted(ids)]
