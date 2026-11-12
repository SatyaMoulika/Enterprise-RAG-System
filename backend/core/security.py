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
