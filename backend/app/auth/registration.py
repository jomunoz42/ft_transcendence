"""Registering a user: checks the input, then creates the user and their profile together.

The route layer calls this and commits; this module only flushes.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.db.models import Profile, User
from app import errors


def normalize_email(email: str) -> str:
    """The form every email is stored and looked up in: stripped and lowercase."""
    return email.strip().lower()


def _looks_like_email(email: str) -> bool:
    """Loose format check: ASCII only, one @, something before it, a dot after it, no spaces or NUL."""
    local, at, domain = email.partition("@")
    return (
        email.isascii()
        and bool(at and local)
        and "@" not in domain
        and "." in domain
        and not domain.startswith(".")
        and not domain.endswith(".")
        and not any(c.isspace() for c in email)
        and "\x00" not in email
    )


def register_user(session: Session, email: str, password: str, display_name: str) -> User:
    """Create a user and their profile. Raises on bad input or duplicate email; never commits."""
    email = normalize_email(email)
    if not _looks_like_email(email):
        raise errors.http_422_registration("email", "not a valid email address")
    if not 8 <= len(password) <= 128:
        raise errors.http_422_registration("password", "must be 8 to 128 characters")
    display_name = display_name.strip()
    if not display_name:
        raise errors.http_422_registration("display_name", "required")
    if "\x00" in display_name:
        raise errors.http_422_registration("display_name", "contains a NUL character")
    user = User(email=email, password_hash=hash_password(password))
    user.profile = Profile(display_name=display_name)
    session.flush()  # keep: the caller's pending errors must not be blamed on this insert
    try:
        with session.begin_nested():
            session.add(user)
    except IntegrityError:
        raise errors.HTTP_409_EMAIL_TAKEN from None
    return user
