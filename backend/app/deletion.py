"""Signed deletion challenges and one-transaction account erasure."""

import base64
import datetime
import hashlib
import hmac
import json
import os
import secrets

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import DeletionRequest, Notification, User
from app.notifications import MESSAGES

TOKEN_PURPOSE = "account_deletion"
TOKEN_LIFETIME = datetime.timedelta(minutes=15)
REQUEST_COOLDOWN = datetime.timedelta(minutes=5)


class DeletionConfigurationError(Exception):
    pass


class InvalidDeletionToken(Exception):
    pass


class DeletionRateLimited(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after


def now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class DeletionTokenCodec:
    def __init__(self, secret: bytes):
        if len(secret) < 32:
            raise DeletionConfigurationError()
        self.secret = secret

    @classmethod
    def from_environment(cls) -> "DeletionTokenCodec":
        secret = os.environ.get("PRIVACY_TOKEN_SECRET", "").encode("utf-8")
        return cls(secret)

    def _email_tag(self, email: str) -> str:
        return hmac.new(self.secret, b"email:" + email.encode("utf-8"), hashlib.sha256).hexdigest()

    def issue(self, user: User, now: datetime.datetime) -> tuple[str, datetime.datetime]:
        expires_at = now + TOKEN_LIFETIME
        payload = {
            "version": 1,
            "purpose": TOKEN_PURPOSE,
            "user_id": user.id,
            "email_tag": self._email_tag(user.email),
            "expires_at": int(expires_at.timestamp()),
            "nonce": secrets.token_urlsafe(24),
        }
        encoded = _encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        signature = _encode(hmac.new(self.secret, encoded.encode("ascii"), hashlib.sha256).digest())
        return f"{encoded}.{signature}", expires_at

    def verify(self, token: str, user: User, now: datetime.datetime) -> None:
        if len(token) > 2048:
            raise InvalidDeletionToken()
        try:
            encoded, signature = token.split(".")
            expected = hmac.new(self.secret, encoded.encode("ascii"), hashlib.sha256).digest()
            if not hmac.compare_digest(_decode(signature), expected):
                raise InvalidDeletionToken()
            payload = json.loads(_decode(encoded))
            valid = (
                type(payload) is dict
                and payload.get("version") == 1
                and payload.get("purpose") == TOKEN_PURPOSE
                and type(payload.get("user_id")) is int
                and payload["user_id"] == user.id
                and type(payload.get("expires_at")) is int
                and now.timestamp() < payload["expires_at"]
                and type(payload.get("email_tag")) is str
                and hmac.compare_digest(payload["email_tag"], self._email_tag(user.email))
            )
            if not valid:
                raise InvalidDeletionToken()
        except (ValueError, UnicodeError, KeyError, TypeError, base64.binascii.Error):
            raise InvalidDeletionToken() from None


def _lock_active_user(session: Session, user_id: int) -> User:
    user = session.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None or user.deleted_at is not None:
        raise InvalidDeletionToken()
    return user


def create_deletion_request(
    session: Session, user_id: int, codec: DeletionTokenCodec,
) -> tuple[str, str, datetime.datetime]:
    """Stage a new challenge; the route sends email before committing it."""
    user = _lock_active_user(session, user_id)
    now = now_utc()
    row = session.get(DeletionRequest, user_id)
    if row is not None and now < row.requested_at + REQUEST_COOLDOWN:
        remaining = row.requested_at + REQUEST_COOLDOWN - now
        raise DeletionRateLimited(max(1, int(remaining.total_seconds()) + 1))
    token, expires_at = codec.issue(user, now)
    if row is None:
        row = DeletionRequest(user_id=user_id, token_hash="", requested_at=now, expires_at=expires_at)
        session.add(row)
    row.token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    row.requested_at = now
    row.expires_at = expires_at
    session.flush()
    return token, user.email, expires_at


def delete_user_row(session: Session, user_id: int) -> None:
    """Let PostgreSQL apply the existing CASCADE and SET NULL FK rules."""
    session.execute(delete(User).where(User.id == user_id))


def confirm_and_delete(
    session: Session, user_id: int, token: str, codec: DeletionTokenCodec,
) -> str:
    """Erase the account and anonymize retained notifications; caller commits."""
    user = _lock_active_user(session, user_id)
    now = now_utc()
    codec.verify(token, user, now)
    row = session.get(DeletionRequest, user_id)
    if (
        row is None or now >= row.expires_at
        or not hmac.compare_digest(row.token_hash, hashlib.sha256(token.encode("ascii")).hexdigest())
    ):
        raise InvalidDeletionToken()

    # Recipient-owned history survives, but no actor ID, source key or custom
    # message can retain data about the account being removed.
    affected = session.scalars(
        select(Notification).where(Notification.actor_id == user_id).with_for_update()
    ).all()
    for notification in affected:
        notification.actor_id = None
        notification.event_key = f"gdpr:removed-actor:{notification.id}"
        notification.message = MESSAGES.get(notification.event_type, "Notification")
    session.flush()

    email = user.email
    delete_user_row(session, user_id)
    return email
