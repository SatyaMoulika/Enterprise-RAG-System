from sqlalchemy.orm import Session
from models.enterprise import Enterprise

class EnterpriseRepository:

    @staticmethod
    def create(db: Session, enterprise: Enterprise) -> Enterprise:
        db.add(enterprise)
        db.commit()
        db.refresh(enterprise)
        return enterprise

    @staticmethod
    def get_by_name(db: Session,name: str):
        return (
            db.query(Enterprise)
            .filter(
                Enterprise.name == name
            )
            .first()
        )

    @staticmethod
    def get_by_id(db: Session, enterprise_id: int):
        return (
            db.query(Enterprise)
            .filter(
                Enterprise.id == enterprise_id
            )
            .first()
        )