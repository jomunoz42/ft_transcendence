"""Auth routes (issue #15): a thin HTTP layer over app.auth. These routes commit; app.auth never does."""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.current_user import current_user
from app.auth.login import InvalidCredentials, authenticate
from app.auth.registration import EmailTaken, InvalidRegistration, register_user
from app.auth.sessions import SESSION_LIFETIME, end_session, start_session
from app.db import get_session, _public
from app.db.models import User
from app.realtime.notifications import LogoutNotifier, get_logout_notifier

router = APIRouter()

class RegisterBody(BaseModel):
    email: str
    password: str
    display_name: str


class LoginBody(BaseModel):
    email: str
    password: str

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterBody, session: Session = Depends(get_session)) -> dict:
    """Create an account and its profile; 201 with the public user, 422 naming the bad field, 409 if the email is taken."""
    try:
        user = register_user(session, body.email, body.password, body.display_name)
    except InvalidRegistration as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, {"field": error.field, "reason": error.reason}
        ) from None
    except EmailTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
    session.commit()
    return _public(user)


@router.post("/login")
def login(body: LoginBody, response: Response, session: Session = Depends(get_session)) -> dict:
    """Log in; 200 with the public user and the session cookie set, 401 for any refusal."""
    try:
        user = authenticate(session, body.email, body.password)
    except InvalidCredentials:
        session.commit()  # keep: saves the failed-attempt count, or the lockout never triggers
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password") from None
    token = start_session(session, user)
    session.commit()
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return _public(user)


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    """The logged-in user; 401 without a valid session cookie."""
    return _public(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session: Session = Depends(get_session),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    notify_logout: LogoutNotifier = Depends(get_logout_notifier),
) -> None:
    """End this browser's session and clear its cookie; 204 even if it was not logged in."""
    if token:
        end_session(session, token)
        session.commit()
        notify_logout(token)
    response.delete_cookie(SESSION_COOKIE_NAME, httponly=True, secure=True, samesite="lax")
