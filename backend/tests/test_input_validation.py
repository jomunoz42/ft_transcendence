"""Bad and malicious input on every route that takes a body, query or path value, through the real app (#50).

The rule tested: a bad value gets a 4xx, never a 500, and hostile text (SQL, HTML)
is stored and returned as plain data. Registration's own field rules are covered in
test_register_user.py and test_auth_routes.py; this file covers the other routes.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

API = "/api/v1"
ALICE = {"email": "alice@x.com", "password": "hunter22", "display_name": "Alice"}
BOB = {"email": "bob@x.com", "password": "hunter33", "display_name": "Bob"}
TOO_BIG_ID = 2**63  # one past PostgreSQL BIGINT
SQL = "Robert'); DROP TABLE users;--"
HTML = "<script>alert(1)</script>"


def browser() -> TestClient:
    """A browser that sees a server error as a 500 response instead of a raised exception."""
    return TestClient(app, base_url="https://testserver", raise_server_exceptions=False)


def log_in(user: dict) -> tuple[TestClient, int]:
    """A browser with `user` registered and logged in, and their id."""
    b = browser()
    user_id = b.post(f"{API}/auth/register", json=user).json()["id"]
    b.post(f"{API}/auth/login", json={"email": user["email"], "password": user["password"]})
    return b, user_id


@pytest.fixture
def friends(client):
    """Alice and Bob logged in in their own browsers and friends; (alice, bob, bob_id)."""
    alice, alice_id = log_in(ALICE)
    bob, bob_id = log_in(BOB)
    alice.post(f"{API}/friends/request/{bob_id}")
    bob.post(f"{API}/friends/accept/{alice_id}")
    return alice, bob, bob_id


BAD_LOGINS = [
    {},
    {"email": "alice@x.com"},
    {"email": None, "password": None},
    {"email": "alice@x.com", "password": 12345678},
    {"email": "alice\x00@x.com", "password": "hunter22"},
    {"email": "alice@x.com", "password": "x" * 100_000},
]


@pytest.mark.parametrize("body", BAD_LOGINS, ids=range(len(BAD_LOGINS)))
def test_a_bad_login_body_is_refused_without_a_server_error(client, body):
    response = browser().post(f"{API}/auth/login", json=body)

    assert 400 <= response.status_code < 500


BAD_SETTINGS = [
    {"email": "not-an-email"},
    {"email": ""},
    {"email": "bob@x.com"},  # already Bob's
    {"password": "short"},
    {"password": "x" * 129},
    {"email": "alice\x00@x.com"},
]


@pytest.mark.parametrize("body", BAD_SETTINGS, ids=range(len(BAD_SETTINGS)))
def test_settings_refuse_what_registration_refuses(friends, body):
    alice, _, _ = friends

    response = alice.post(f"{API}/settings", json=body)

    assert 400 <= response.status_code < 500


BAD_PROFILES = [
    {"display_name": ""},
    {"display_name": "   "},
    {"display_name": "Al\x00ice"},
    {"bio": "b\x00io"},
    {"is_top10_public": "maybe"},
]


@pytest.mark.parametrize("body", BAD_PROFILES, ids=range(len(BAD_PROFILES)))
def test_a_bad_profile_update_is_refused_without_a_server_error(friends, body):
    alice, _, _ = friends

    response = alice.post(f"{API}/profiles/me", json=body)

    assert 400 <= response.status_code < 500


BAD_COMMENTS = [{}, {"body": ""}, {"body": "   "}, {"body": None}, {"body": "hi\x00"}]


@pytest.mark.parametrize("body", BAD_COMMENTS, ids=range(len(BAD_COMMENTS)))
def test_a_bad_comment_is_refused_without_a_server_error(friends, body):
    alice, _, bob_id = friends

    response = alice.post(f"{API}/profiles/{bob_id}/comments", json=body)

    assert 400 <= response.status_code < 500


@pytest.mark.parametrize("body", [{}, {"reaction": "love"}, {"reaction": None}], ids=range(3))
def test_a_bad_reaction_is_refused_without_a_server_error(friends, body):
    alice, _, bob_id = friends

    response = alice.post(f"{API}/profiles/{bob_id}/reactions", json=body)

    assert 400 <= response.status_code < 500


BAD_PATHS = [
    ("POST", "/friends/request/{id}"),
    ("POST", "/friends/accept/{id}"),
    ("POST", "/friends/block/{id}"),
    ("DELETE", "/friends/{id}"),
    ("GET", "/profiles/{id}"),
    ("GET", "/profiles/{id}/comments"),
    ("POST", "/profiles/{id}/reactions"),
    ("GET", "/songs/{id}"),
]


@pytest.mark.parametrize("bad_id", ["abc", "-1", str(TOO_BIG_ID)])
@pytest.mark.parametrize(("method", "path"), BAD_PATHS, ids=[f"{m} {p}" for m, p in BAD_PATHS])
def test_a_bad_id_in_the_path_is_refused_without_a_server_error(friends, method, path, bad_id):
    alice, _, _ = friends

    response = alice.request(method, API + path.format(id=bad_id), json={"reaction": "like"})

    assert 400 <= response.status_code < 500


@pytest.mark.parametrize("text", [SQL, HTML])
def test_hostile_text_is_stored_and_returned_as_plain_data(friends, text):
    alice, bob, bob_id = friends

    alice.post(f"{API}/profiles/{bob_id}/comments", json={"body": text})
    registered = browser().post(f"{API}/auth/register", json={"email": "carol@x.com", "password": "hunter44", "display_name": text})

    assert [c["body"] for c in alice.get(f"{API}/profiles/{bob_id}/comments").json()] == [text]
    assert registered.status_code == 201
    assert registered.json()["display_name"] == text
    assert bob.get(f"{API}/auth/me").status_code == 200  # users table still there
