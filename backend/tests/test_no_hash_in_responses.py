"""Every route that can return user data, called through the real app: no response may contain a password hash (#50)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

API = "/api/v1"
ALICE = {"email": "alice@x.com", "password": "hunter22", "display_name": "Alice"}
BOB = {"email": "bob@x.com", "password": "hunter33", "display_name": "Bob"}

ROUTES = [
    ("POST", "/auth/register", {"email": "carol@x.com", "password": "hunter44", "display_name": "Carol"}),
    ("POST", "/auth/login", {"email": "alice@x.com", "password": "hunter22"}),
    ("GET", "/auth/me", None),
    ("GET", "/settings", None),
    ("POST", "/settings", {}),
    ("GET", "/profiles", None),
    ("GET", "/profiles/me", None),
    ("POST", "/profiles/me", {}),
    ("GET", "/profiles/{bob}", None),
    ("GET", "/profiles/{bob}/comments", None),
    ("GET", "/profiles/{bob}/reactions", None),
    ("POST", "/profiles/{bob}/comments", {"body": "nice list"}),
    ("POST", "/profiles/{bob}/reactions", {"reaction": "like"}),
    ("GET", "/friends", None),
    ("GET", "/friends/requests", None),
    ("GET", "/friends/blocks", None),
]


@pytest.fixture
def alice(client):
    """Alice logged in, friends with Bob; Bob has commented on and reacted to her Top 10."""
    bob = TestClient(app, base_url="https://testserver")
    client.post(f"{API}/auth/register", json=ALICE)
    bob_id = bob.post(f"{API}/auth/register", json=BOB).json()["id"]
    alice_id = client.post(f"{API}/auth/login", json={"email": ALICE["email"], "password": ALICE["password"]}).json()["id"]
    bob.post(f"{API}/auth/login", json={"email": BOB["email"], "password": BOB["password"]})
    client.post(f"{API}/friends/request/{bob_id}")
    bob.post(f"{API}/friends/accept/{alice_id}")
    bob.post(f"{API}/profiles/{alice_id}/comments", json={"body": "great taste"})
    bob.post(f"{API}/profiles/{alice_id}/reactions", json={"reaction": "like"})
    return client, bob_id


@pytest.mark.parametrize(("method", "path", "body"), ROUTES, ids=[f"{m} {p}" for m, p, _ in ROUTES])
def test_no_response_contains_a_password_hash(alice, method, path, body):
    client, bob_id = alice

    response = client.request(method, API + path.format(bob=bob_id), json=body, follow_redirects=True)

    assert response.status_code < 500
    assert "password_hash" not in response.text
    assert "$argon2" not in response.text
