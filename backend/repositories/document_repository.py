from sqlalchemy.orm import Session
from models.document import Document


class DocumentRepository:

    @staticmethod
    def create(db: Session, document: Document):
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    @staticmethod
    def get_by_enterprise(db: Session, enterprise_id: int):
        return db.query(Document).filter(
            Document.enterprise_id == enterprise_id
        ).all()
    
    @staticmethod
    def delete(db, document_id, enterprise_id):

        document = (
            db.query(Document).filter(
                Document.id == document_id,
                Document.enterprise_id == enterprise_id
            ).first()
        )

        if not document:
            return False

        db.delete(document)
        db.commit()

        return True