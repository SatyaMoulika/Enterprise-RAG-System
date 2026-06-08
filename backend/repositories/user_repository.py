from sqlalchemy.orm import Session
from models.user import User


class UserRepository:

    @staticmethod
    def get_by_email(db: Session, email: str, enterprise_id: int | None = None):
        query = db.query(User).filter(User.email == email)

        if enterprise_id:
            query = query.filter(User.enterprise_id == enterprise_id)

        return query.first()

    @staticmethod
    def create(db: Session, user: User) -> User:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_by_id(db: Session, user_id: int, enterprise_id: int):
        return (
            db.query(User)
            .filter(User.id == user_id, User.enterprise_id == enterprise_id)
            .first()
        )

    @staticmethod
    def get_all(db: Session, enterprise_id: int):
        return db.query(User).filter(User.enterprise_id == enterprise_id).all()

    @staticmethod
    def delete(db: Session, user_id: int, enterprise_id: int):
        user = db.query(User).filter(
            User.id == user_id,
            User.enterprise_id == enterprise_id
        ).first()

        if not user:
            return False

        db.delete(user)
        db.commit()
        return True