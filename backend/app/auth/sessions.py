"""Login sessions: start one at login, find its user on each request, end it at logout.

The browser keeps a random token in a cookie; the database keeps only its SHA-256 hash.
"""

import datetime
import hashlib
import secrets

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import User, UserSession

SESSION_LIFETIME = datetime.timedelta(days=7)


def _hash(token: str) -> str:
    """The SHA-256 hex digest stored in `sessions.token_hash`."""
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(session: Session, user: User) -> str:
    """Create a session for this user and return the raw token for the cookie.

    Also deletes this user's expired sessions. Never commits.
    """
    session.execute(
        delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at <= func.now())
    )
    token = secrets.token_urlsafe(32)
    # Seconds, not the timedelta: Postgres reads "7 days" as calendar days and stretches them over a clock change.
    lifetime = func.make_interval(0, 0, 0, 0, 0, 0, SESSION_LIFETIME.total_seconds())
    session.add(UserSession(user_id=user.id, token_hash=_hash(token), expires_at=func.now() + lifetime))
    session.flush()
    return token


def user_for_token(session: Session, token: str | None) -> User | None:
    """The user this token logs in, or None if it is missing, unknown, expired, or the user is deleted."""
    if not token:
        return
    return session.scalar(
        select(User)
        .join(UserSession)
        .where(
            UserSession.token_hash == _hash(token),
            UserSession.expires_at > func.now(),
            User.deleted_at.is_(None),
        )
    )


def end_session(session: Session, token: str) -> None:
    """Log this token out. An unknown or already-ended token is ignored. Never commits."""
    session.execute(delete(UserSession).where(UserSession.token_hash == _hash(token)))
