"""Every route that can return user data, called through the real app: no response may contain a password hash (#50)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

API = "/api/v1"
ALICE = {"email": "alice@x.com", "password": "hunter22", "display_name": "Alice"}
BOB = {"email": "bob@x.com", "password": "hunter33", "display_name": "Bob"}

ROUTES = [
    ("POST", "/auth/register", {"email": "carol@x.com", "password": "hunter44", "display_name": "Carol"}, 201),
    ("POST", "/auth/login", {"email": "alice@x.com", "password": "hunter22"}, 200),
    ("GET", "/auth/me", None, 200),
    ("GET", "/settings", None, 200),
    ("POST", "/settings", {}, 200),
    ("GET", "/profiles", None, 200),
    ("GET", "/profiles/me", None, 200),
    ("POST", "/profiles/me", {}, 200),
    ("GET", "/profiles/{bob}", None, 200),
    ("GET", "/profiles/{bob}/comments", None, 200),
    ("GET", "/profiles/{bob}/reactions", None, 200),
    ("POST", "/profiles/{bob}/comments", {"body": "nice list"}, 200),
    ("POST", "/profiles/{bob}/reactions", {"reaction": "like"}, 200),
    ("POST", "/profiles/{bob}/comments/{comment}", {"body": "edited"}, 200),
    ("POST", "/profiles/{bob}/comments/latest", {"body": "edited again"}, 200),
    ("GET", "/friends", None, 200),
    ("GET", "/friends/requests", None, 200),
    ("GET", "/friends/blocks", None, 200),
]


@pytest.fixture
def alice(client):
    """Alice logged in, friends with Bob; each commented on the other's Top 10, Bob also reacted to hers.

    Gives (Alice's browser, path values: Bob's id and Alice's comment id).
    """
    bob = TestClient(app, base_url="https://testserver")
    client.post(f"{API}/auth/register", json=ALICE)
    bob_id = bob.post(f"{API}/auth/register", json=BOB).json()["id"]
    alice_id = client.post(f"{API}/auth/login", json={"email": ALICE["email"], "password": ALICE["password"]}).json()["id"]
    bob.post(f"{API}/auth/login", json={"email": BOB["email"], "password": BOB["password"]})
    client.post(f"{API}/friends/request/{bob_id}")
    bob.post(f"{API}/friends/accept/{alice_id}")
    bob.post(f"{API}/profiles/{alice_id}/comments", json={"body": "great taste"})
    bob.post(f"{API}/profiles/{alice_id}/reactions", json={"reaction": "like"})
    client.post(f"{API}/profiles/{bob_id}/comments", json={"body": "nice list"})
    comment_id = client.get(f"{API}/profiles/{bob_id}/comments").json()[0]["id"]
    return client, {"bob": bob_id, "comment": comment_id}


@pytest.mark.parametrize(("method", "path", "body", "status"), ROUTES, ids=[f"{m} {p}" for m, p, _, _ in ROUTES])
def test_no_response_contains_a_password_hash(alice, method, path, body, status):
    client, ids = alice

    response = client.request(method, API + path.format(**ids), json=body, follow_redirects=True)

    assert response.status_code == status, response.text
    assert "password_hash" not in response.text
    assert "$argon2" not in response.text
