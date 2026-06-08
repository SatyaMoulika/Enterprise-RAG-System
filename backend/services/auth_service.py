from core.security import hash_password, verify_password, create_access_token
from models.user import User
from repositories.user_repository import UserRepository
from services.enterprise_service import EnterpriseService


class AuthService:

    @staticmethod
    def register_user(db, enterprise_name, email, password):

        existing_user = UserRepository.get_by_email(db, email)

        if existing_user:
            raise ValueError("User already exists")

        enterprise = EnterpriseService.create_enterprise(db, enterprise_name)

        user = User(
            enterprise_id=enterprise.id,
            email=email,
            hashed_password=hash_password(password),
            role="admin"
        )

        user = UserRepository.create(db, user)

        token = create_access_token({
            "sub": user.email,
            "user_id": str(user.id),
            "enterprise_id": str(user.enterprise_id),
            "role": user.role,
        })

        return {
            "user": user,
            "access_token": token,
            "token_type": "bearer"
        }

    @staticmethod
    def login_user(db, email, password):

        user = UserRepository.get_by_email(db, email)

        if not user or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid credentials")

        token = create_access_token({
            "sub": user.email,
            "user_id": str(user.id),
            "enterprise_id": str(user.enterprise_id),
            "role": user.role,
        })

        return {
            "access_token": token,
            "token_type": "bearer"
        }