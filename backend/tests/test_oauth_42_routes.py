"""The 42 login routes under /api/v1/auth/42, called through the real app with the 42 API faked."""

import datetime
from urllib.parse import parse_qs, urlsplit

import pytest

from app.auth.ft42_client import Ft42Error
from app.auth.oauth import login_with_42
from app.auth.registration import register_user
from app.main import app
from app.routes.v1.oauth import ft42_profile

START = "/api/v1/auth/42"
CALLBACK = "/api/v1/auth/42/callback"
ME = "/api/v1/auth/me"
PROFILE = {"id": 4242, "login": "alencart", "email": "alencart@student.42.fr"}


@pytest.fixture(autouse=True)
def ft42_env(monkeypatch):
    monkeypatch.setenv("FT42_CLIENT_ID", "the-client-id")
    monkeypatch.setenv("FT42_CLIENT_SECRET", "the-client-secret")
    monkeypatch.setenv("FT42_REDIRECT_URI", "https://localhost/api/v1/auth/42/callback")
    monkeypatch.setenv("FRONTEND_URL", "https://localhost")


def test_starting_a_42_login_redirects_to_42_with_the_state_kept_in_a_cookie(client):
    response = client.get(START, follow_redirects=False)

    assert response.is_redirect
    url = urlsplit(response.headers["location"])
    query = {key: values[0] for key, values in parse_qs(url.query).items()}
    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://api.intra.42.fr/oauth/authorize"
    assert query == {
        "client_id": "the-client-id",
        "redirect_uri": "https://localhost/api/v1/auth/42/callback",
        "response_type": "code",
        "state": query["state"],
    }
    assert response.cookies["oauth_state"] == query["state"]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie and "max-age=600" in cookie


def come_back_from_42(client, answer=PROFILE, cookie="the-state", **params):
    """Call the callback as 42 would, with the 42 API answering `answer` (a profile, or an exception to raise)."""

    def fetch(code):
        if isinstance(answer, Exception):
            raise answer
        return answer

    app.dependency_overrides[ft42_profile] = lambda: fetch
    if cookie:
        client.cookies.set("oauth_state", cookie)
    query = {"code": "the-code", "state": "the-state", **params}
    return client.get(CALLBACK, params={k: v for k, v in query.items() if v is not None}, follow_redirects=False)


def test_coming_back_from_42_logs_in_and_sends_the_browser_to_the_frontend(client):
    response = come_back_from_42(client)

    assert response.is_redirect
    assert response.headers["location"] == "https://localhost"
    assert client.get(ME).json()["email"] == "alencart@student.42.fr"
    assert any(h.startswith('oauth_state=""') for h in response.headers.get_list("set-cookie"))


def assert_sent_back_to_login_with(client, response, error):
    assert response.is_redirect
    assert response.headers["location"] == f"https://localhost/login?error={error}"
    assert client.get(ME).status_code == 401
    assert any(h.startswith('oauth_state=""') for h in response.headers.get_list("set-cookie"))


@pytest.mark.parametrize(
    "case, error",
    [
        ({"error": "access_denied", "code": None}, "oauth_denied"),
        ({"error": "server_error", "code": None}, "provider_error"),
        ({"state": "another-state"}, "state_mismatch"),
        ({"state": None}, "state_mismatch"),
        ({"cookie": None}, "state_mismatch"),
        ({"code": None}, "provider_error"),
        ({"answer": Ft42Error("401 from /oauth/token")}, "provider_error"),
        ({"answer": {**PROFILE, "email": None}}, "email_missing"),
    ],
)
def test_a_failed_42_login_sends_the_browser_back_to_login_with_the_reason(client, case, error):
    response = come_back_from_42(client, **case)

    assert_sent_back_to_login_with(client, response, error)


def test_the_42_account_of_a_deleted_user_sends_back_account_deleted(client, session):
    user = login_with_42(session, PROFILE)
    user.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    session.commit()

    response = come_back_from_42(client)

    assert_sent_back_to_login_with(client, response, "account_deleted")


def test_a_42_email_already_used_by_a_password_account_sends_back_email_taken(client, session):
    register_user(session, "alencart@student.42.fr", "hunter22", "André")
    session.commit()

    response = come_back_from_42(client)

    assert_sent_back_to_login_with(client, response, "email_taken")
