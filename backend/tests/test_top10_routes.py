"""Top 10 route tests — CRUD, rank swap, visibility, and ownership."""

import pytest
from app.db.models import Profile

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
COOKIE = "myplaylist_session"

ALICE = {"email": "alice@test.com", "password": "hunter22", "display_name": "Alice"}
BOB = {"email": "bob@test.com", "password": "hunter22", "display_name": "Bob"}

SONG_A = {"provider_id": "sp-aaa", "title": "Song A", "artist": "Artist A"}
SONG_B = {"provider_id": "sp-bbb", "title": "Song B", "artist": "Artist B"}
SONG_C = {"provider_id": "sp-ccc", "title": "Song C", "artist": "Artist C"}


def _register_and_login(client, user):
    res = client.post(REGISTER, json=user)
    user_id = res.json()["id"]
    client.post(LOGIN, json={"email": user["email"], "password": user["password"]})
    return user_id


def _top10_url(user_id):
    return f"/api/v1/profiles/{user_id}/top10"


# ── CRUD ──────────────────────────────────────────────────────────────

def test_add_a_song_to_top10(client):
    uid = _register_and_login(client, ALICE)
    res = client.post(_top10_url(uid), json={"song": SONG_A, "rank": 1})
    assert res.status_code == 200, f"got {res.status_code}: {res.json()}"
    body = res.json()
    assert "rank" in body, f"missing 'rank' in response: {body}"
    assert body["rank"] == 1


def test_list_top10_returns_entries_in_rank_order(client):
    uid = _register_and_login(client, ALICE)
    client.post(_top10_url(uid), json={"song": SONG_B, "rank": 3})
    client.post(_top10_url(uid), json={"song": SONG_A, "rank": 1})

    res = client.get(_top10_url(uid))
    assert res.status_code == 200
    ranks = [e["rank"] for e in res.json()]
    assert ranks == [1, 3]


def test_get_single_top10_entry(client):
    uid = _register_and_login(client, ALICE)
    entry_id = client.post(_top10_url(uid), json={"song": SONG_A, "rank": 1}).json()["id"]

    res = client.get(f"{_top10_url(uid)}/{entry_id}")
    assert res.status_code == 200
    assert res.json()["id"] == entry_id


def test_delete_top10_entry(client):
    uid = _register_and_login(client, ALICE)
    entry_id = client.post(_top10_url(uid), json={"song": SONG_A, "rank": 1}).json()["id"]

    res = client.delete(f"{_top10_url(uid)}/{entry_id}")
    assert res.status_code == 200

    res = client.get(f"{_top10_url(uid)}/{entry_id}")
    assert res.status_code == 404


# ── Rank swap (regression for UniqueViolation) ───────────────────────

def test_swapping_two_occupied_ranks_does_not_violate_unique_constraint(client):
    uid = _register_and_login(client, ALICE)
    e1 = client.post(_top10_url(uid), json={"song": SONG_A, "rank": 1}).json()
    e2 = client.post(_top10_url(uid), json={"song": SONG_B, "rank": 2}).json()

    # Move rank 1 to rank 2 — should swap via delete+reinsert
    res = client.post(f"{_top10_url(uid)}/{e1['id']}", json={"rank": 2})
    assert res.status_code == 200

    entries = client.get(_top10_url(uid)).json()
    by_song = {e["song_id"]: e["rank"] for e in entries}
    assert by_song[e1["song_id"]] == 2
    assert by_song[e2["song_id"]] == 1


def test_moving_to_an_empty_rank_does_not_swap(client):
    uid = _register_and_login(client, ALICE)
    e1 = client.post(_top10_url(uid), json={"song": SONG_A, "rank": 1}).json()

    res = client.post(f"{_top10_url(uid)}/{e1['id']}", json={"rank": 5})
    assert res.status_code == 200
    assert res.json()["rank"] == 5


def test_moving_to_same_rank_is_a_noop(client):
    uid = _register_and_login(client, ALICE)
    e1 = client.post(_top10_url(uid), json={"song": SONG_A, "rank": 3}).json()

    res = client.post(f"{_top10_url(uid)}/{e1['id']}", json={"rank": 3})
    assert res.status_code == 200
    assert res.json()["rank"] == 3


# ── Conflict checks ──────────────────────────────────────────────────

def test_duplicate_song_is_rejected(client):
    uid = _register_and_login(client, ALICE)
    client.post(_top10_url(uid), json={"song": SONG_A, "rank": 1})

    res = client.post(_top10_url(uid), json={"song": SONG_A, "rank": 2})
    assert res.status_code == 409


def test_duplicate_rank_is_rejected(client):
    uid = _register_and_login(client, ALICE)
    client.post(_top10_url(uid), json={"song": SONG_A, "rank": 1})

    res = client.post(_top10_url(uid), json={"song": SONG_B, "rank": 1})
    assert res.status_code == 409


def test_eleventh_entry_is_rejected(client, session):
    uid = _register_and_login(client, ALICE)
    for i in range(1, 11):
        res = client.post(_top10_url(uid), json={
            "song": {"provider_id": f"sp-fill-{i}", "title": f"Fill {i}", "artist": "Filler"},
            "rank": i,
        })
        assert res.status_code == 200, f"rank {i} failed: {res.json()}"

    res = client.post(_top10_url(uid), json={
        "song": {"provider_id": "sp-overflow", "title": "Overflow", "artist": "Filler"},
        "rank": 1,
    })
    assert res.status_code == 409


# ── Ownership ─────────────────────────────────────────────────────────

def test_cannot_add_to_another_users_top10(client):
    alice_id = _register_and_login(client, ALICE)
    bob_id = _register_and_login(client, BOB)

    res = client.post(_top10_url(alice_id), json={"song": SONG_A, "rank": 1})
    assert res.status_code == 422


def test_cannot_delete_another_users_entry(client):
    alice_id = _register_and_login(client, ALICE)
    # Add as Alice
    entry_id = client.post(_top10_url(alice_id), json={"song": SONG_A, "rank": 1}).json()["id"]
    # Login as Bob
    _register_and_login(client, BOB)

    res = client.delete(f"{_top10_url(alice_id)}/{entry_id}")
    assert res.status_code == 422


# ── Visibility ────────────────────────────────────────────────────────

def test_non_friend_cannot_see_private_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    client.post(_top10_url(alice_id), json={"song": SONG_A, "rank": 1})
    # Make sure Alice's top10 is private
    session.query(Profile).filter(Profile.user_id == alice_id).update({"is_top10_public": False})
    session.commit()

    # Bob is not friends with Alice
    _register_and_login(client, BOB)
    res = client.get(_top10_url(alice_id))
    assert res.status_code == 403


def test_public_top10_is_visible_to_non_friend(client, session):
    alice_id = _register_and_login(client, ALICE)
    client.post(_top10_url(alice_id), json={"song": SONG_A, "rank": 1})
    # Make Alice's top10 public
    session.query(Profile).filter(Profile.user_id == alice_id).update({"is_top10_public": True})
    session.commit()

    # Bob is not friends with Alice
    _register_and_login(client, BOB)
    res = client.get(_top10_url(alice_id))
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_owner_always_sees_own_top10(client, session):
    alice_id = _register_and_login(client, ALICE)
    client.post(_top10_url(alice_id), json={"song": SONG_A, "rank": 1})
    # Even if private
    session.query(Profile).filter(Profile.user_id == alice_id).update({"is_top10_public": False})
    session.commit()

    res = client.get(_top10_url(alice_id))
    assert res.status_code == 200
    assert len(res.json()) == 1
