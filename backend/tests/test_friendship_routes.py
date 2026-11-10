"""Friendship HTTP routes under /api/v1/friends, called through the real app as a logged-in user."""

import pytest

FRIENDS = "/api/v1/friends"
PASSWORD = "hunter22"


def register(client, name):
    email = f"{name.lower()}@myplaylist.test"
    user_id = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "display_name": name}).json()["id"]
    return user_id


def login_as(client, name):
    client.post("/api/v1/auth/login", json={"email": f"{name.lower()}@myplaylist.test", "password": PASSWORD})


@pytest.fixture
def alice_and_bob(client):
    """Alice and Bob registered; Alice logged in."""
    alice, bob = register(client, "Alice"), register(client, "Bob")
    login_as(client, "Alice")
    return alice, bob


def test_friend_routes_need_a_login(client):
    assert client.get(FRIENDS).status_code == 401


def test_a_request_shows_up_on_both_sides_and_accepting_makes_friends(client, alice_and_bob):
    alice, bob = alice_and_bob

    sent = client.post(f"{FRIENDS}/request/{bob}")
    assert (sent.status_code, sent.json()) == (200, {"status": "pending"})
    assert client.get(f"{FRIENDS}/requests").json() == {
        "incoming": [], "outgoing": [{"id": bob, "display_name": "Bob"}],
    }

    login_as(client, "Bob")
    assert client.get(f"{FRIENDS}/requests").json()["incoming"] == [{"id": alice, "display_name": "Alice"}]
    accepted = client.post(f"{FRIENDS}/accept/{alice}")
    assert (accepted.status_code, accepted.json()) == (200, {"status": "accepted"})
    assert client.get(FRIENDS).json() == [{"id": alice, "display_name": "Alice"}]


def test_asking_back_answers_accepted(client, alice_and_bob):
    alice, bob = alice_and_bob
    client.post(f"{FRIENDS}/request/{bob}")
    login_as(client, "Bob")

    assert client.post(f"{FRIENDS}/request/{alice}").json() == {"status": "accepted"}


def test_declining_a_request(client, alice_and_bob):
    alice, bob = alice_and_bob
    client.post(f"{FRIENDS}/request/{bob}")
    login_as(client, "Bob")

    declined = client.post(f"{FRIENDS}/decline/{alice}")

    assert (declined.status_code, declined.json()) == (200, {"status": "declined"})
    assert client.get(f"{FRIENDS}/requests").json() == {"incoming": [], "outgoing": []}


def test_cancelling_my_request(client, alice_and_bob):
    alice, bob = alice_and_bob
    client.post(f"{FRIENDS}/request/{bob}")

    cancelled = client.post(f"{FRIENDS}/cancel/{bob}")

    assert (cancelled.status_code, cancelled.json()) == (200, {"status": "cancelled"})
    assert client.get(f"{FRIENDS}/requests").json() == {"incoming": [], "outgoing": []}


def test_removing_a_friend(client, alice_and_bob):
    alice, bob = alice_and_bob
    client.post(f"{FRIENDS}/request/{bob}")
    login_as(client, "Bob")
    client.post(f"{FRIENDS}/accept/{alice}")

    removed = client.delete(f"{FRIENDS}/{alice}")

    assert (removed.status_code, removed.json()) == (200, {"status": "removed"})
    assert client.get(FRIENDS).json() == []


def test_blocking_hides_the_block_from_the_blocked_user_and_asks_the_blocker_to_unblock(client, alice_and_bob):
    alice, bob = alice_and_bob

    assert client.post(f"{FRIENDS}/block/{bob}").json() == {"status": "blocked"}
    assert client.post(f"{FRIENDS}/block/{bob}").json() == {"status": "blocked"}

    asked_by_blocker = client.post(f"{FRIENDS}/request/{bob}")
    assert (asked_by_blocker.status_code, asked_by_blocker.json()) == (409, {"detail": "unblock first"})

    login_as(client, "Bob")
    asked_by_blocked = client.post(f"{FRIENDS}/request/{alice}")
    assert (asked_by_blocked.status_code, asked_by_blocked.json()) == (404, {"detail": "Not found"})


def test_unblocking(client, alice_and_bob):
    alice, bob = alice_and_bob
    client.post(f"{FRIENDS}/block/{bob}")

    unblocked = client.post(f"{FRIENDS}/unblock/{bob}")

    assert (unblocked.status_code, unblocked.json()) == (200, {"status": "unblocked"})
    assert client.post(f"{FRIENDS}/unblock/{bob}").status_code == 404


def test_nothing_to_act_on_is_not_found(client, alice_and_bob):
    alice, bob = alice_and_bob

    assert client.post(f"{FRIENDS}/accept/{bob}").status_code == 404
    assert client.post(f"{FRIENDS}/request/{bob + 1000}").status_code == 404


@pytest.mark.parametrize("method, action", [
    ("post", "request"), ("post", "accept"), ("post", "decline"), ("post", "cancel"),
    ("delete", ""), ("post", "block"), ("post", "unblock"),
])
def test_acting_on_myself_is_refused(client, alice_and_bob, method, action):
    alice, _ = alice_and_bob
    path = f"{FRIENDS}/{action}/{alice}" if action else f"{FRIENDS}/{alice}"

    assert getattr(client, method)(path).status_code == 422
