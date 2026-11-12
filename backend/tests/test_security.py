from datetime import timedelta

import bcrypt
import pytest

from core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_argon_hash_and_verification():
    hashed = hash_password("test password")
    assert hashed.startswith("$argon2id$")
    assert verify_password("test password", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("password", "invalid hash")


def test_existing_bcrypt_hash_remains_usable():
    hashed = bcrypt.hashpw(b"existing password", bcrypt.gensalt()).decode()
    assert verify_password("existing password", hashed)
    assert not verify_password("x" * 73, hashed)


def test_expired_and_tampered_tokens_are_rejected():
    with pytest.raises(ValueError):
        decode_access_token(
            create_access_token({"sub": "owner@example.com"}, timedelta(seconds=-1))
        )
    with pytest.raises(ValueError):
        decode_access_token("invalid")


def test_valid_token():
    assert (
        decode_access_token(create_access_token({"sub": "owner@example.com"}))["sub"]
        == "owner@example.com"
    )
