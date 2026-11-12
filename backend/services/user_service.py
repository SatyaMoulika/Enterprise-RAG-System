from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from core.security import hash_password
from models.enterprise import Enterprise
from models.user import User
from repositories.user_repository import UserRepository


class UserService:
    @staticmethod
    def _lock_and_authorize(db, current_user):
        actor_id, enterprise_id = current_user.id, current_user.enterprise_id
        # Serialize membership writes in one workspace. Re-read the actor after waiting:
        # another administrator may have removed this account while its request queued.
        db.execute(select(Enterprise.id).where(Enterprise.id == enterprise_id).with_for_update())
        actor = db.scalar(
            select(User)
            .where(User.id == actor_id, User.enterprise_id == enterprise_id)
            .execution_options(populate_existing=True)
        )
        if actor is None or not actor.is_active or actor.role != "admin":
            raise PermissionError("Administrator access is no longer available")
        return enterprise_id

    @staticmethod
    def create_user(db, email, password, role, current_user):
        password_hash = hash_password(password)
        enterprise_id = UserService._lock_and_authorize(db, current_user)
        if UserRepository.get_by_email(db, email):
            raise ValueError("An account already uses this email")
        user = User(
            email=email, hashed_password=password_hash, role=role, enterprise_id=enterprise_id
        )
        try:
            return UserRepository.create(db, user)
        except IntegrityError:
            db.rollback()
            raise ValueError("An account already uses this email") from None

    @staticmethod
    def get_all_users(db, enterprise_id):
        return UserRepository.get_all(db, enterprise_id)

    @staticmethod
    def get_user_by_id(db, user_id, enterprise_id):
        return UserRepository.get_by_id(db, user_id, enterprise_id)

    @staticmethod
    def delete_user(db, user_id, current_user):
        enterprise_id = UserService._lock_and_authorize(db, current_user)
        target = UserRepository.get_by_id(db, user_id, enterprise_id)
        if target is None:
            return False
        if target.id == current_user.id:
            raise ValueError("You cannot remove your own account")
        if target.role == "admin" and target.is_active:
            count = db.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.enterprise_id == enterprise_id,
                    User.role == "admin",
                    User.is_active.is_(True),
                )
            )
            if count <= 1:
                raise ValueError("The workspace must retain an active administrator")
        db.delete(target)
        db.commit()
        return True
