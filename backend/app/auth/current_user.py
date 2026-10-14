"""The current_user dependency: every protected route gets the logged-in user or a 401."""

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.sessions import user_for_token
from app.db import get_session
from app.db.models import User

SESSION_COOKIE = "session"


def current_user(
    session: Session = Depends(get_session),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> User:
    """The user the session cookie logs in; 401 if the cookie is missing, unknown, or expired."""
    user = user_for_token(session, token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")
    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User was deleted") # TODO: Find the right return
    return user
