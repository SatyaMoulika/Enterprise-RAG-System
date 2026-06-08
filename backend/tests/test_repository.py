from database.session import SessionLocal
from models.user import User
from repositories.user_repository import UserRepository

db = SessionLocal()

user = User(
    email="repo@test.com",
    hashed_password="dummy"
)

UserRepository.create(
    db=db,
    user=user
)

found = UserRepository.get_by_email(
    db=db,
    email="repo@test.com"
)

print(found.email)