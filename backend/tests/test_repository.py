from models.enterprise import Enterprise
from models.user import User
from repositories.user_repository import UserRepository


def test_user_lookup_is_tenant_scoped(db):
    workspace = Enterprise(name="test")
    db.add(workspace)
    db.flush()
    user = User(
        enterprise_id=workspace.id, email="repo@example.com", hashed_password="not-a-real-hash"
    )
    db.add(user)
    db.commit()
    assert UserRepository.get_by_email(db, user.email, workspace.id).id == user.id
    assert UserRepository.get_by_email(db, user.email, workspace.id + 1) is None
