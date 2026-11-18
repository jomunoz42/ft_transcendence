"""The 42 API client (profile_from_code), against a fake 42 server built with httpx.MockTransport."""

import httpx
import pytest

from app.auth.ft42_client import Ft42Error, profile_from_code

ME = {"id": 4242, "login": "alencart", "email": "alencart@student.42.fr"}


@pytest.fixture(autouse=True)
def ft42_env(monkeypatch):
    monkeypatch.setenv("FT42_CLIENT_ID", "the-client-id")
    monkeypatch.setenv("FT42_CLIENT_SECRET", "the-client-secret")
    monkeypatch.setenv("FT42_REDIRECT_URI", "https://localhost/api/v1/auth/42/callback")


def fake_42(token_status=200, me_status=200):
    """An httpx client whose requests go to a fake 42 that records them."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/oauth/token":
            return httpx.Response(token_status, json={"access_token": "the-access-token"})
        if request.url.path == "/v2/me":
            return httpx.Response(me_status, json=ME)
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def test_a_valid_code_gives_the_42_profile():
    http, _ = fake_42()

    assert profile_from_code("the-code", http) == ME


def test_the_code_is_traded_with_the_app_credentials_and_the_token_reads_the_profile():
    http, seen = fake_42()

    profile_from_code("the-code", http)

    token_request, me_request = seen
    assert (token_request.method, str(token_request.url)) == ("POST", "https://api.intra.42.fr/oauth/token")
    assert dict(httpx.QueryParams(token_request.content.decode())) == {
        "grant_type": "authorization_code",
        "client_id": "the-client-id",
        "client_secret": "the-client-secret",
        "code": "the-code",
        "redirect_uri": "https://localhost/api/v1/auth/42/callback",
    }
    assert (me_request.method, str(me_request.url)) == ("GET", "https://api.intra.42.fr/v2/me")
    assert me_request.headers["Authorization"] == "Bearer the-access-token"


@pytest.mark.parametrize("token_status, me_status", [(401, 200), (200, 500)])
def test_a_refusal_from_42_raises_ft42_error(token_status, me_status):
    http, _ = fake_42(token_status, me_status)

    with pytest.raises(Ft42Error):
        profile_from_code("the-code", http)


def test_42_being_unreachable_raises_ft42_error():
    def unreachable(request):
        raise httpx.ConnectError("no route to api.intra.42.fr")

    with pytest.raises(Ft42Error):
        profile_from_code("the-code", httpx.Client(transport=httpx.MockTransport(unreachable)))
