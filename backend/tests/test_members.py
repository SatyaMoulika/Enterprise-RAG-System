from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.security import create_access_token
from models.user import User
from repositories.user_repository import UserRepository


def add(client, account, email="member@example.com", role="employee"):
    return client.post(
        "/users/create_user",
        headers=account,
        json={"email": email, "password": "initial password 123", "role": role},
    )


def login(client, email="member@example.com"):
    response = client.post("/auth/login", json={"email": email, "password": "initial password 123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_can_create_and_list_members_without_exposing_credentials(client, account):
    result = add(client, account)
    assert result.status_code == 200, result.text
    assert result.json()["role"] == "employee"
    assert result.json()["is_active"] is True
    members = client.get("/users/get_all_users", headers=account)
    assert members.status_code == 200
    assert {m["email"] for m in members.json()} == {"owner@example.com", "member@example.com"}
    assert all("hashed_password" not in m and "account_stamp" not in m for m in members.json())


def test_membership_operations_are_admin_only(client, account):
    member = add(client, account).json()
    headers = login(client)
    assert client.get("/users/get_all_users", headers=headers).status_code == 403
    assert add(client, headers, "new@example.com").status_code == 403
    assert client.delete(f"/users/delete_user/{member['id']}", headers=headers).status_code == 403


def test_member_lists_and_removal_are_tenant_scoped(client, account):
    member = add(client, account).json()
    other = client.post(
        "/auth/register",
        json={
            "enterprise_name": "Other team",
            "email": "other@example.com",
            "password": "other password 123",
        },
    )
    headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert [row["email"] for row in client.get("/users/get_all_users", headers=headers).json()] == [
        "other@example.com"
    ]
    assert client.delete(f"/users/delete_user/{member['id']}", headers=headers).status_code == 404
    assert client.get(f"/users/get_user/{member['id']}", headers=headers).status_code == 404


def test_self_removal_is_blocked_and_the_administrator_remains(client, account):
    owner = client.get("/users/me", headers=account).json()
    response = client.delete(f"/users/delete_user/{owner['id']}", headers=account)
    assert response.status_code == 409
    assert "own account" in response.json()["detail"]
    assert client.get("/users/me", headers=account).status_code == 200
    assert len(client.get("/users/get_all_users", headers=account).json()) == 1


def test_another_administrator_can_be_removed(client, account):
    result = add(client, account, "admin@example.com", role="admin")
    assert result.status_code == 200
    assert (
        client.delete(f"/users/delete_user/{result.json()['id']}", headers=account).status_code
        == 200
    )
    assert client.get("/users/me", headers=account).status_code == 200


def test_removed_token_cannot_authenticate_even_when_email_and_id_are_reused(client, account):
    old = add(client, account).json()
    old_headers = login(client)
    assert client.delete(f"/users/delete_user/{old['id']}", headers=account).status_code == 200
    assert client.get("/users/me", headers=old_headers).status_code == 401
    assert client.get("/documents/list", headers=old_headers).status_code == 401
    new = add(client, account, role="admin").json()
    # SQLite can reuse its highest integer primary key; the account stamp must still differ.
    assert new["id"] == old["id"]
    assert client.get("/users/me", headers=old_headers).status_code == 401
    assert client.get("/users/me", headers=login(client)).status_code == 200


def test_duplicate_email_returns_conflict_without_adding_a_member(client, account):
    assert add(client, account).status_code == 200
    assert add(client, account).status_code == 409
    assert len(client.get("/users/get_all_users", headers=account).json()) == 2


def test_uniqueness_race_is_rolled_back_and_reported_as_conflict(client, account, monkeypatch):
    original = UserRepository.create

    def conflict(*args, **kwargs):
        raise IntegrityError("insert", {}, Exception("synthetic uniqueness conflict"))

    monkeypatch.setattr(UserRepository, "create", conflict)
    assert add(client, account).status_code == 409
    monkeypatch.setattr(UserRepository, "create", original)
    assert add(client, account).status_code == 200


def test_role_and_password_validation(client, account):
    response = client.post(
        "/users/create_user",
        headers=account,
        json={"email": "member@example.com", "password": "short", "role": "superadmin"},
    )
    assert response.status_code == 422


def test_pre_upgrade_email_only_tokens_require_sign_in_again(client, account):
    token = create_access_token({"sub": "owner@example.com"})
    assert client.get("/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_inactive_member_status_is_real_server_data(client, account, db):
    member = add(client, account).json()
    record = db.scalar(select(User).where(User.id == member["id"]))
    record.is_active = False
    db.commit()
    rows = client.get("/users/get_all_users", headers=account).json()
    assert next(row for row in rows if row["id"] == member["id"])["is_active"] is False
