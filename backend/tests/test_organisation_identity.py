import pytest
from sqlalchemy import func, select

from models.enterprise import Enterprise
from models.user import User


def test_signup_saves_administrator_name_and_returns_organisation_in_profile(client, db):
    response = client.post(
        "/auth/register",
        json={
            "enterprise_name": "  Aster Technologies  ",
            "name": "  Moulika Devi  ",
            "is_admin": True,
            "email": "admin@aster.example.com",
            "password": "administrator password 123",
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    profile = client.get("/users/me", headers=headers).json()
    assert profile["name"] == "Moulika Devi"
    assert profile["enterprise_name"] == "Aster Technologies"
    assert profile["role"] == "admin"
    assert db.scalar(select(User.name)) == "Moulika Devi"
    assert db.scalar(select(Enterprise.name)) == "Aster Technologies"
    login = client.post(
        "/auth/login",
        json={"email": "admin@aster.example.com", "password": "administrator password 123"},
    )
    assert login.status_code == 200
    assert (
        client.get(
            "/users/me", headers={"Authorization": "Bearer " + login.json()["access_token"]}
        ).json()["name"]
        == "Moulika Devi"
    )


def test_members_share_their_actual_organisation_name_and_cannot_override_it(client, account):
    owner = client.get("/users/me", headers=account).json()
    created = client.post(
        "/users/create_user",
        headers=account,
        json={
            "name": "Alice Morgan",
            "email": "alice@aster.example.com",
            "password": "employee password 123",
            "role": "employee",
            "enterprise_name": "Forged organisation",
        },
    )
    assert created.status_code == 200, created.text
    token = client.post(
        "/auth/login",
        json={"email": "alice@aster.example.com", "password": "employee password 123"},
    ).json()["access_token"]
    profile = client.get("/users/me", headers={"Authorization": "Bearer " + token}).json()
    assert profile["name"] == "Alice Morgan"
    assert profile["role"] == "employee"
    assert profile["enterprise_name"] == owner["enterprise_name"] == "Example workspace"
    foreign = client.post(
        "/auth/register",
        json={
            "enterprise_name": "Another organisation",
            "name": "Bob Reed",
            "email": "bob@other.example.com",
            "password": "administrator password 123",
        },
    )
    assert foreign.status_code == 201, foreign.text
    other = client.get(
        "/users/me", headers={"Authorization": "Bearer " + foreign.json()["access_token"]}
    ).json()
    assert other["enterprise_name"] == "Another organisation"
    assert other["enterprise_id"] != profile["enterprise_id"]


@pytest.mark.parametrize(
    "override", [{"name": ""}, {"name": "   "}, {"name": "x" * 121}, {"is_admin": False}]
)
def test_invalid_signup_identity_does_not_create_accounts_or_organisations(client, db, override):
    response = client.post(
        "/auth/register",
        json={
            "enterprise_name": "Aster",
            "name": "Moulika Devi",
            "is_admin": True,
            "email": "admin@aster.example.com",
            "password": "administrator password 123",
            **override,
        },
    )
    assert response.status_code == 422, response.text
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert db.scalar(select(func.count()).select_from(Enterprise)) == 0


def test_existing_unnamed_accounts_keep_their_profile_and_organisation(client, account):
    profile = client.get("/users/me", headers=account).json()
    assert profile["name"] == ""
    assert profile["enterprise_name"] == "Example workspace"
