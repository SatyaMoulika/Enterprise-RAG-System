import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jose import JWTError, jwt

from core.config import settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    # Preserve sign-in for existing bcrypt hashes; new passwords use Argon2id.
    if hashed.startswith(("$2a$", "$2b$", "$2y$")):
        raw = password.encode("utf-8")
        if len(raw) > 72:
            return False
        try:
            return bcrypt.checkpw(raw, hashed.encode("utf-8"))
        except ValueError:
            return False
    try:
        return _password_hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    claims = data.copy()
    now = datetime.now(UTC)
    claims.update(
        {
            "iat": now,
            "exp": now
            + (
                expires_delta
                if expires_delta is not None
                else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            ),
        }
    )
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require_exp": True, "require_sub": True},
        )
    except JWTError as exc:
        raise ValueError("Invalid token") from exc


def _account_stamp(user_id: int, password_hash: str) -> str:
    # A recreated account has a new salted password hash, even if email/ID are reused.
    return hmac.new(
        settings.JWT_SECRET_KEY.encode(), f"{user_id}:{password_hash}".encode(), hashlib.sha256
    ).hexdigest()


def create_user_access_token(email: str, user_id: int, password_hash: str) -> str:
    return create_access_token(
        {
            "sub": email,
            "user_id": str(user_id),
            "account_stamp": _account_stamp(user_id, password_hash),
        }
    )


def token_matches_account(payload: dict, user_id: int, password_hash: str) -> bool:
    stamp = payload.get("account_stamp")
    return (
        payload.get("user_id") == str(user_id)
        and isinstance(stamp, str)
        and hmac.compare_digest(stamp, _account_stamp(user_id, password_hash))
    )
