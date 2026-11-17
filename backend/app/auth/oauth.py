"""Logging in with a 42 account: turns the profile 42 returns into a local user.

The route layer calls this and commits; this module only flushes.
"""

import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.registration import _looks_like_email, normalize_email
from app.db.models import OAuthAccount, Profile, User
from app import errors

PROVIDER_42 = "42"


def new_state() -> str:
    """A random, unguessable value for the OAuth `state` cookie and redirect parameter."""
    return secrets.token_urlsafe(32)


def state_matches(cookie: str | None, query: str | None) -> bool:
    """True only when both states are present and equal; compared in constant time."""
    return bool(cookie and query) and secrets.compare_digest(cookie, query)


def login_with_42(session: Session, profile: dict) -> User:
    """The local user for a 42 profile (`id`, `login`, `email` from /v2/me), created without a password on first login; 422 if the email is missing or invalid, 409 if a password account has it. Never commits."""
    link = session.get(OAuthAccount, (PROVIDER_42, str(profile["id"])))
    if link is not None:
        return link.user
    email = normalize_email(profile.get("email") or "")
    if not _looks_like_email(email):
        raise errors.http_422_registration("email", "missing or invalid in the 42 profile")
    user = User(email=email, password_hash=None)
    user.profile = Profile(display_name=profile["login"])
    session.flush()  # keep: the caller's pending errors must not be blamed on this insert
    try:
        with session.begin_nested():
            session.add(OAuthAccount(provider=PROVIDER_42, provider_id=str(profile["id"]), user=user))
    except IntegrityError:
        raise errors.HTTP_409_EMAIL_TAKEN from None
    return user
