from datetime import timedelta

import pytest
from sqlalchemy import select

from core.config import settings
from core.security import _account_stamp, create_access_token
from models.user import User
from services import password_reset_service as recovery


@pytest.fixture
def mail(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "mail.example.invalid")
    monkeypatch.setattr(settings, "SMTP_FROM", "noreply@example.com")
    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "https://atlas.example.com")
    messages = []
    monkeypatch.setattr(
        recovery, "send_reset_email", lambda email, token: messages.append((email, token))
    )
    return messages


def test_reset_is_single_use_revokes_old_sessions_and_cannot_authenticate_as_access_token(
    client, account, mail
):
    assert (
        client.post("/auth/forgot-password", json={"email": "owner@example.com"}).status_code == 200
    )
    token = mail[0][1]
    assert client.get("/users/me", headers={"Authorization": "Bearer " + token}).status_code == 401
    response = client.post(
        "/auth/reset-password", json={"token": token, "password": "new-password-123"}
    )
    assert response.status_code == 200, response.text
    assert client.get("/users/me", headers=account).status_code == 401
    assert (
        client.post(
            "/auth/login", json={"email": "owner@example.com", "password": "test password 123"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login", json={"email": "owner@example.com", "password": "new-password-123"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/auth/reset-password", json={"token": token, "password": "other-password-123"}
        ).status_code
        == 400
    )


def test_unknown_address_and_cooldown_have_same_response_and_no_token_in_api(client, account, mail):
    known = client.post("/auth/forgot-password", json={"email": "owner@example.com"})
    unknown = client.post("/auth/forgot-password", json={"email": "missing@example.com"})
    repeat = client.post("/auth/forgot-password", json={"email": "owner@example.com"})
    assert known.json() == unknown.json() == repeat.json()
    assert len(mail) == 1
    assert mail[0][1] not in known.text


def test_expired_token_and_access_token_are_not_reset_credentials(client, account, db, mail):
    user = db.scalar(select(User))
    expired = create_access_token(
        {
            "sub": user.email,
            "user_id": str(user.id),
            "account_stamp": _account_stamp(user.id, user.hashed_password),
            "purpose": "password_reset",
        },
        timedelta(minutes=-1),
    )
    for token in [expired, account["Authorization"].split()[1], "invalid"]:
        assert (
            client.post(
                "/auth/reset-password", json={"token": token, "password": "new-password-123"}
            ).status_code
            == 400
        )
    assert client.get("/users/me", headers=account).status_code == 200


def test_disabled_account_cannot_request_or_use_reset(client, account, db, mail):
    client.post("/auth/forgot-password", json={"email": "owner@example.com"})
    user = db.scalar(select(User))
    user.is_active = False
    db.commit()
    client.post("/auth/forgot-password", json={"email": "owner@example.com"})
    assert len(mail) == 1
    assert (
        client.post(
            "/auth/reset-password", json={"token": mail[0][1], "password": "new-password-123"}
        ).status_code
        == 400
    )


def test_missing_mail_configuration_is_explicit_for_every_email(client, account, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    for email in ["owner@example.com", "missing@example.com"]:
        response = client.post("/auth/forgot-password", json={"email": email})
        assert response.status_code == 503 and "not configured" in response.json()["detail"]


def test_smtp_message_uses_configured_origin_and_token_fragment(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM", "noreply@example.com")
    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "https://atlas.example.com")
    sent = []

    class SMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def starttls(self, **kwargs):
            pass

        def login(self, *a):
            pass

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(recovery.smtplib, "SMTP", SMTP)
    recovery.send_reset_email("employee@example.com", "test-token")
    assert "https://atlas.example.com/reset-password#token=test-token" in sent[0].get_content()
    assert sent[0]["To"] == "employee@example.com"


@pytest.fixture
def local_reset(monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_DIRECT_PASSWORD_RESET", True)
    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "http://localhost:8080")
    monkeypatch.setattr(settings, "SMTP_HOST", "")

    def unexpected_email(*args):
        pytest.fail("Direct reset must not send email")

    monkeypatch.setattr(recovery, "send_reset_email", unexpected_email)


def test_direct_reset_without_smtp_changes_password_and_revokes_sessions(
    client, account, local_reset
):
    assert client.get("/auth/config").json()["direct_password_reset_enabled"] is True
    response = client.post(
        "/auth/reset-password/direct",
        json={"email": "owner@example.com", "password": "direct-password-123"},
    )
    assert response.status_code == 200, response.text
    assert client.get("/users/me", headers=account).status_code == 401
    assert (
        client.post(
            "/auth/login", json={"email": "owner@example.com", "password": "test password 123"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/login", json={"email": "owner@example.com", "password": "direct-password-123"}
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "enabled, origin",
    [
        (False, "http://localhost:8080"),
        (True, "https://atlas.example.com"),
        (True, "http://atlas.example.com"),
        (True, "http://localhost.attacker.example"),
    ],
)
def test_direct_reset_is_blocked_outside_local_mode(client, account, monkeypatch, enabled, origin):
    monkeypatch.setattr(settings, "LOCAL_DIRECT_PASSWORD_RESET", enabled)
    monkeypatch.setattr(settings, "PUBLIC_APP_URL", origin)
    assert client.get("/auth/config").json()["direct_password_reset_enabled"] is False
    response = client.post(
        "/auth/reset-password/direct",
        json={"email": "owner@example.com", "password": "direct-password-123"},
    )
    assert response.status_code == 403
    assert client.get("/users/me", headers=account).status_code == 200


def test_direct_reset_rejects_missing_inactive_and_invalid_accounts(
    client, account, db, local_reset
):
    for email, password in [
        ("invalid", "direct-password-123"),
        ("owner@example.com", "short"),
    ]:
        assert (
            client.post(
                "/auth/reset-password/direct", json={"email": email, "password": password}
            ).status_code
            == 422
        )
    assert client.get("/users/me", headers=account).status_code == 200
    user = db.scalar(select(User))
    original_hash = user.hashed_password
    user.is_active = False
    db.commit()
    for email in ["missing@example.com", "owner@example.com"]:
        assert (
            client.post(
                "/auth/reset-password/direct",
                json={"email": email, "password": "direct-password-123"},
            ).status_code
            == 400
        )
    db.refresh(user)
    assert user.hashed_password == original_hash
