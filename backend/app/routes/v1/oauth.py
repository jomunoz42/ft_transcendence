"""42 login routes (issue #17): send the browser to 42, then turn 42's answer into a session. These routes commit."""

import logging
import os
from collections.abc import Callable, Iterator
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.ft42_client import Ft42Error, profile_from_code
from app.auth.oauth import login_with_42, new_state, state_matches
from app.auth.sessions import set_session_cookie, start_session
from app.db import get_session

router = APIRouter()
logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://api.intra.42.fr/oauth/authorize"
STATE_COOKIE = "oauth_state"
STATE_LIFETIME_SECONDS = 600  # room for a first 42 sign-in with 2FA and the consent page
REFUSAL_REASONS = {
    status.HTTP_403_FORBIDDEN: "account_deleted",
    status.HTTP_409_CONFLICT: "email_taken",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "email_missing",
}


def ft42_profile() -> Iterator[Callable[[str], dict]]:
    """Dependency: a function turning a 42 callback code into the /v2/me profile, over one HTTP client per request."""
    with httpx.Client(timeout=10) as http:
        yield lambda code: profile_from_code(code, http)


@router.get("/42")
def start_42_login() -> RedirectResponse:
    """Redirect to 42's consent page; the `state` it echoes back is kept in a short-lived cookie."""
    state = new_state()
    query = urlencode(
        {
            "client_id": os.environ["FT42_CLIENT_ID"],
            "redirect_uri": os.environ["FT42_REDIRECT_URI"],
            "response_type": "code",
            "state": state,
        }
    )
    response = RedirectResponse(f"{AUTHORIZE_URL}?{query}")
    response.set_cookie(
        STATE_COOKIE, state, max_age=STATE_LIFETIME_SECONDS, httponly=True, secure=True, samesite="lax"
    )
    return response


@router.get("/42/callback")
def finish_42_login(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    state_cookie: str | None = Cookie(default=None, alias=STATE_COOKIE),
    session: Session = Depends(get_session),
    fetch_profile: Callable[[str], dict] = Depends(ft42_profile),
) -> RedirectResponse:
    """Log in the 42 user who just consented and redirect to the frontend with the session cookie set.

    Any failure redirects to FRONTEND_URL/login?error=<reason> instead: oauth_denied, state_mismatch,
    provider_error, account_deleted, email_taken or email_missing. The state cookie is cleared either way.
    """
    if not state_matches(state_cookie, state):
        return _back_to_login("state_mismatch")
    if error:
        return _back_to_login("oauth_denied" if error == "access_denied" else "provider_error")
    if not code:
        return _back_to_login("provider_error")
    try:
        user = login_with_42(session, fetch_profile(code))
    except Ft42Error as failure:
        logger.warning("42 login failed: %s", failure)
        return _back_to_login("provider_error")
    except HTTPException as refusal:
        return _back_to_login(REFUSAL_REASONS.get(refusal.status_code, "provider_error"))
    token = start_session(session, user)
    session.commit()
    response = _clear_state(RedirectResponse(os.environ["FRONTEND_URL"]))
    set_session_cookie(response, token)
    return response


def _back_to_login(reason: str) -> RedirectResponse:
    """Redirect to the frontend login page with the failure reason, clearing the state cookie."""
    return _clear_state(RedirectResponse(f"{os.environ['FRONTEND_URL']}/login?{urlencode({'error': reason})}"))


def _clear_state(response: RedirectResponse) -> RedirectResponse:
    """The same response with the single-use state cookie deleted."""
    response.delete_cookie(STATE_COOKIE, httponly=True, secure=True, samesite="lax")
    return response
