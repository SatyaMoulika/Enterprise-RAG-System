from sqlalchemy.exc import IntegrityError

from core.security import create_user_access_token, hash_password, verify_password
from models.enterprise import Enterprise
from models.user import User
from repositories.user_repository import UserRepository


class AuthService:
    @staticmethod
    def register_user(db, enterprise_name, email, password):
        # One transaction: a failed account cannot leave an orphan workspace.
        if UserRepository.get_by_email(db, email):
            raise ValueError("Account or workspace already exists")
        try:
            enterprise = Enterprise(name=enterprise_name)
            db.add(enterprise)
            db.flush()
            user = User(
                enterprise_id=enterprise.id,
                email=email,
                hashed_password=hash_password(password),
                role="admin",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            raise ValueError("Account or workspace already exists") from None
        return {
            "user": user,
            "access_token": create_user_access_token(user.email, user.id, user.hashed_password),
            "token_type": "bearer",
        }

    @staticmethod
    def login_user(db, email, password):
        user = UserRepository.get_by_email(db, email)
        if not user or not user.is_active or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid credentials")
        return {
            "access_token": create_user_access_token(user.email, user.id, user.hashed_password),
            "token_type": "bearer",
        }
