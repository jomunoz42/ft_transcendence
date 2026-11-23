"""Two users logged in at the same time through the real app, each with their own cookie jar (#50)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"
PROFILE_ME = "/api/v1/profiles/me"
ALICE = {"email": "alice@x.com", "password": "hunter22", "display_name": "Alice"}
BOB = {"email": "bob@x.com", "password": "hunter33", "display_name": "Bob"}


@pytest.fixture
def other_browser(client):
    """A second browser: same app and test database as `client`, separate cookies."""
    return TestClient(app, base_url="https://testserver")


def log_in(browser, user: dict) -> int:
    """Register and log in `user` in this browser; their id."""
    user_id = browser.post(REGISTER, json=user).json()["id"]
    browser.post(LOGIN, json={"email": user["email"], "password": user["password"]})
    return user_id


def test_two_users_stay_logged_in_at_once_and_each_sees_only_themselves(client, other_browser):
    alice_id = log_in(client, ALICE)
    bob_id = log_in(other_browser, BOB)

    assert client.get(ME).json() == {"id": alice_id, "email": "alice@x.com", "display_name": "Alice"}
    assert other_browser.get(ME).json() == {"id": bob_id, "email": "bob@x.com", "display_name": "Bob"}


def test_one_user_logging_out_keeps_the_other_logged_in(client, other_browser):
    log_in(client, ALICE)
    bob_id = log_in(other_browser, BOB)

    client.post(LOGOUT)

    assert client.get(ME).status_code == 401
    assert other_browser.get(ME).json()["id"] == bob_id


def test_each_user_gets_their_own_profile_from_profiles_me(client, other_browser):
    log_in(client, ALICE)
    log_in(other_browser, BOB)

    assert client.get(PROFILE_ME).json()["display_name"] == "Alice"
    assert other_browser.get(PROFILE_ME).json()["display_name"] == "Bob"
