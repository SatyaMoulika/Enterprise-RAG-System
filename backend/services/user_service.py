from core.security import hash_password
from repositories.user_repository import UserRepository
from models.user import User


class UserService:

    @staticmethod
    def create_user(db, email, password, role, current_user):

        enterprise_id = current_user.enterprise_id

        existing = UserRepository.get_by_email(
            db,
            email,
            enterprise_id
        )

        if existing:
            raise Exception("User already exists in this enterprise")

        user = User(
            email=email,
            hashed_password=hash_password(password),
            role=role,
            enterprise_id=enterprise_id
        )

        return UserRepository.create(db, user)

    @staticmethod
    def get_all_users(db, enterprise_id):
        return UserRepository.get_all(db, enterprise_id)

    @staticmethod
    def get_user_by_id(db, user_id, enterprise_id):
        return UserRepository.get_by_id(db, user_id, enterprise_id)

    @staticmethod
    def delete_user(db, user_id, enterprise_id):
        return UserRepository.delete(db, user_id, enterprise_id)