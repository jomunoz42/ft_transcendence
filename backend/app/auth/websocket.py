from sqlalchemy.exc import SQLAlchemyError

from app.auth.sessions import user_for_token
from app.db import SessionLocal


def authenticate_websocket(token: str | None) -> int | None:
    """Return the authenticated user ID, or None for an invalid token."""
    if not token:
        return None

    with SessionLocal() as session:
        user = user_for_token(session, token)
        return user.id if user is not None else None
