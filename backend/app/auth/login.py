"""Logging in: checks email and password, counts failures, and locks the account after too many."""

import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.auth.registration import normalize_email
from app.db.models import User

MAX_FAILED_ATTEMPTS = 5
LOCKOUT = datetime.timedelta(minutes=15)
_DUMMY_HASH = hash_password("no account has this password")


class InvalidCredentials(Exception):
    """Login refused. Deliberately the same for every reason, so nothing about the account leaks."""


def authenticate(session: Session, email: str, password: str) -> User:
    """The user these credentials belong to, else InvalidCredentials; the caller must commit even then."""
    row = session.execute(
        select(User, func.coalesce(User.locked_until > func.now(), False))
        .where(User.email == normalize_email(email), User.deleted_at.is_(None))
        .with_for_update()
    ).one_or_none()
    user, locked = row if row else (None, False)
    if user is None or locked:
        verify_password(password, _DUMMY_HASH)  # keep: every refusal must take as long as a wrong password
        raise InvalidCredentials()
    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
            user.locked_until = func.now() + LOCKOUT
            user.failed_login_count = 0
        session.flush()
        raise InvalidCredentials()
    user.failed_login_count = 0
    user.locked_until = None
    session.flush()
    return user
