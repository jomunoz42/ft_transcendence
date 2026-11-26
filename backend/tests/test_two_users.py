"""Two users logged in at the same time through the real app, each with their own cookie jar (#50)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"
PROFILE_ME = "/api/v1/profiles/me"
PROFILES = "/api/v1/profiles"
FRIENDS = "/api/v1/friends"
ALICE = {"email": "alice@x.com", "password": "hunter22", "display_name": "Alice"}
BOB = {"email": "bob@x.com", "password": "hunter33", "display_name": "Bob"}
CAROL = {"email": "carol@x.com", "password": "hunter44", "display_name": "Carol"}


@pytest.fixture
def other_browser(client):
    """A second browser: same app and test database as `client`, separate cookies."""
    return TestClient(app, base_url="https://testserver")


@pytest.fixture
def third_browser(client):
    """A third browser with its own cookies, like `other_browser`."""
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


def befriend(asker, asker_id: int, accepter, accepter_id: int) -> None:
    """Make the two logged-in users friends through the friend routes."""
    asker.post(f"{FRIENDS}/request/{accepter_id}")
    accepter.post(f"{FRIENDS}/accept/{asker_id}")


@pytest.fixture
def bob_comments_on_alice(client, other_browser, third_browser):
    """Alice (client), Bob (other_browser) and Carol (third_browser), all friends with Alice; Bob comments on Alice's Top 10.

    Returns the comments URL on Alice's page and the id of Bob's comment.
    """
    alice_id = log_in(client, ALICE)
    bob_id = log_in(other_browser, BOB)
    carol_id = log_in(third_browser, CAROL)
    befriend(client, alice_id, other_browser, bob_id)
    befriend(client, alice_id, third_browser, carol_id)
    comments = f"{PROFILES}/{alice_id}/comments"
    other_browser.post(comments, json={"body": "great taste"})
    return comments, other_browser.get(comments).json()[0]["id"]


def test_the_top10_owner_cannot_edit_someone_elses_comment(client, other_browser, bob_comments_on_alice):
    comments, comment_id = bob_comments_on_alice

    edited = client.post(f"{comments}/{comment_id}", json={"body": "changed by Alice"})

    assert edited.status_code == 404
    assert [c["body"] for c in other_browser.get(comments).json()] == ["great taste"]


def test_a_third_user_cannot_delete_someone_elses_comment(other_browser, third_browser, bob_comments_on_alice):
    comments, comment_id = bob_comments_on_alice

    deleted = third_browser.delete(f"{comments}/{comment_id}")

    assert deleted.status_code == 404
    assert [c["body"] for c in other_browser.get(comments).json()] == ["great taste"]


def test_the_top10_owner_can_delete_a_comment_on_their_page(client, other_browser, bob_comments_on_alice):
    comments, comment_id = bob_comments_on_alice

    deleted = client.delete(f"{comments}/{comment_id}")

    assert deleted.status_code == 200
    assert other_browser.get(comments).json() == []
