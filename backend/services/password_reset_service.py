"""Short-lived reset links, invalidated by an atomic password-hash change."""

import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from urllib.parse import urlsplit

from sqlalchemy import or_, select, update

from core.config import settings
from core.errors import ProviderUnavailable
from core.security import _account_stamp, create_access_token, decode_access_token, hash_password
from models.user import User

REQUEST_MESSAGE = "If an active account exists for that email, a password reset link will be sent. Check your inbox and spam folder."
INVALID_LINK = "This reset link is invalid or expired. Request a new link."


def send_reset_email(email, token):
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = email
    message["Subject"] = "Reset your Atlas password"
    link = settings.PUBLIC_APP_URL.rstrip("/") + "/reset-password#token=" + token
    message.set_content(
        f"A password reset was requested for your Atlas account.\n\nOpen this link to choose a new password:\n{link}\n\nThis link expires in {settings.PASSWORD_RESET_MINUTES} minutes and can be used once. If you did not request this, ignore this message.\n"
    )
    try:
        if settings.SMTP_SECURITY == "ssl":
            connection = smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=15,
                context=ssl.create_default_context(),
            )
        else:
            connection = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        with connection as smtp:
            if settings.SMTP_SECURITY == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        raise ProviderUnavailable(
            "Password reset email is temporarily unavailable. Try again later."
        ) from exc


def deliver_reset(email, token):
    try:
        send_reset_email(email, token)
    except ProviderUnavailable:
        import logging

        logging.getLogger("uvicorn.error").warning("Password reset email delivery failed")


class PasswordResetService:
    @staticmethod
    def direct_enabled():
        origin = urlsplit(settings.PUBLIC_APP_URL)
        return (
            settings.LOCAL_DIRECT_PASSWORD_RESET
            and origin.scheme == "http"
            and origin.hostname in {"localhost", "127.0.0.1", "::1"}
            and not origin.username
            and not origin.password
        )

    @staticmethod
    def reset_direct(db, email, password):
        if not PasswordResetService.direct_enabled():
            raise PermissionError("Direct password reset is disabled.")
        changed = db.execute(
            update(User)
            .where(User.email == email, User.is_active.is_(True))
            .values(hashed_password=hash_password(password), reset_requested_at=None)
        )
        if not changed.rowcount:
            db.rollback()
            raise ValueError("No active account found for this email.")
        db.commit()

    @staticmethod
    def request(db, email, enqueue=None):
        parsed = urlsplit(settings.PUBLIC_APP_URL)
        if (
            not settings.SMTP_HOST
            or not settings.SMTP_FROM
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
            or (
                parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
        ):
            raise ProviderUnavailable(
                "Password reset email is not configured. Contact your administrator."
            )
        now = datetime.now(UTC)
        user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
        if user is None:
            return REQUEST_MESSAGE
        claimed = db.execute(
            update(User)
            .where(
                User.id == user.id,
                User.is_active.is_(True),
                or_(
                    User.reset_requested_at.is_(None),
                    User.reset_requested_at < now - timedelta(seconds=60),
                ),
            )
            .values(reset_requested_at=now)
            .execution_options(synchronize_session=False)
        )
        if not claimed.rowcount:
            db.rollback()
            return REQUEST_MESSAGE
        # Commit the cooldown before delivery to bound concurrent/reset mail requests.
        db.commit()
        token = create_access_token(
            {
                "sub": user.email,
                "user_id": str(user.id),
                "account_stamp": _account_stamp(user.id, user.hashed_password),
                "purpose": "password_reset",
            },
            timedelta(minutes=settings.PASSWORD_RESET_MINUTES),
        )
        if enqueue is not None:
            enqueue(deliver_reset, user.email, token)
        else:
            deliver_reset(user.email, token)
        return REQUEST_MESSAGE

    @staticmethod
    def reset(db, token, password):
        import hmac

        try:
            claims = decode_access_token(token)
            identity = int(claims["user_id"])
            if claims.get("purpose") != "password_reset":
                raise ValueError(INVALID_LINK)
            user = db.scalar(
                select(User).where(
                    User.id == identity, User.email == claims["sub"], User.is_active.is_(True)
                )
            )
            if user is None or not hmac.compare_digest(
                str(claims.get("account_stamp", "")), _account_stamp(user.id, user.hashed_password)
            ):
                raise ValueError(INVALID_LINK)
            old_hash = user.hashed_password
            changed = db.execute(
                update(User)
                .where(
                    User.id == identity, User.is_active.is_(True), User.hashed_password == old_hash
                )
                .values(hashed_password=hash_password(password), reset_requested_at=None)
            )
            if not changed.rowcount:
                db.rollback()
                raise ValueError(INVALID_LINK)
            db.commit()
        except (ValueError, KeyError, TypeError) as exc:
            db.rollback()
            raise ValueError(INVALID_LINK) from exc
