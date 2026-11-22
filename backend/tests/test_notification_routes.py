"""Notification API ownership, pagination, response privacy and read status."""

import datetime

import pytest
from sqlalchemy import select

from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.sessions import end_session, start_session
from app.crud.notification import create_notification
from app.db.models import Notification, User, UserSession

URL = "/api/v1/notifications"


@pytest.fixture
def users(session, client):
    alice = User(email="alice@notification.test", password_hash="private-hash")
    bob = User(email="bob@notification.test", password_hash="other-private-hash")
    session.add_all([alice, bob])
    session.flush()
    client.cookies.set(SESSION_COOKIE_NAME, start_session(session, alice))
    session.commit()
    return alice, bob


def create(session, user, key, actor=None):
    return create_notification(session, user.id, actor_id=actor.id if actor else None,
                               event_key=key, event_type="system", message="A safe summary.")


@pytest.mark.parametrize("method,path", [("get", ""), ("get", "/unread-count"), ("post", "/1/read")])
@pytest.mark.parametrize("state", ["missing", "unknown", "expired", "revoked", "deleted"])
def test_all_endpoints_require_a_live_session(session, client, users, method, path, state):
    alice, _ = users
    token = client.cookies.get(SESSION_COOKIE_NAME)
    if state == "missing":
        client.cookies.clear()
    elif state == "unknown":
        client.cookies.set(SESSION_COOKIE_NAME, "not-a-session")
    elif state == "expired":
        session.scalar(select(UserSession).where(UserSession.user_id == alice.id)).expires_at = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        )
    elif state == "revoked":
        end_session(session, token)
    else:
        alice.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    session.commit()

    assert getattr(client, method)(URL + path).status_code == 401


def test_empty_list_and_count(client, users):
    assert client.get(URL).json() == []
    assert client.get(URL + "/unread-count").json() == {"unread_count": 0}


def test_list_and_count_scope_to_session_and_serialize_only_public_fields(session, client, users):
    alice, bob = users
    mine = create(session, alice, "internal-secret-operation-key", actor=bob)
    theirs = create(session, bob, "other-event", actor=alice)
    mine_id, theirs_id, bob_id = mine.id, theirs.id, bob.id
    session.commit()

    response = client.get(URL, params={"recipient_id": bob_id, "user_id": bob_id})
    assert response.status_code == 200
    rows = response.json()
    assert [row["id"] for row in rows] == [mine_id]
    assert set(rows[0]) == {"id", "actor_id", "event_type", "message", "created_at", "read_at"}
    assert rows[0]["actor_id"] == bob_id
    assert rows[0]["read_at"] is None
    assert client.get(URL + "/unread-count", params={"recipient_id": bob_id}).json() == {"unread_count": 1}

    # Being the actor does not grant ownership; query/body IDs cannot grant it either.
    forbidden = client.post(f"{URL}/{theirs_id}/read", params={"recipient_id": bob_id}, json={"recipient_id": bob_id})
    missing = client.post(f"{URL}/9223372036854775807/read")
    assert (forbidden.status_code, forbidden.json()) == (missing.status_code, missing.json()) == (404, {"detail": "Not found"})
    assert session.get(Notification, theirs_id).read_at is None


def test_pagination_orders_by_time_then_id_and_filters_before_slicing(session, client, users):
    alice, bob = users
    first = create(session, alice, "1")
    second = create(session, alice, "2")
    third = create(session, alice, "3")
    create(session, bob, "4")
    old = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    first.created_at = old + datetime.timedelta(days=1)  # newest time, smallest ID
    second.created_at = third.created_at = old
    expected = [first.id, third.id, second.id]
    session.commit()

    assert [row["id"] for row in client.get(URL).json()] == expected
    assert [row["id"] for row in client.get(URL, params={"limit": 1, "offset": 1}).json()] == expected[1:2]
    assert client.get(URL, params={"offset": 3}).json() == []


def test_default_and_maximum_page_sizes(session, client, users):
    alice, _ = users
    for number in range(101):
        create(session, alice, str(number))
    session.commit()
    assert len(client.get(URL).json()) == 20
    assert len(client.get(URL, params={"limit": 100}).json()) == 100


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": -1}, {"limit": 101}, {"limit": "bad"},
    {"offset": -1}, {"offset": 10001}, {"offset": "bad"},
])
def test_invalid_pagination_is_422(client, users, params):
    assert client.get(URL, params=params).status_code == 422


def test_mark_read_commits_and_retries_keep_first_read_time(session, client, users):
    alice, bob = users
    mine = create(session, alice, "mine")
    other = create(session, bob, "other")
    mine_id, other_id = mine.id, other.id
    session.commit()

    response = client.post(f"{URL}/{mine_id}/read")
    assert response.status_code == 200
    assert response.json()["read_at"] is not None
    assert client.post(f"{URL}/{mine_id}/read").json() == response.json()
    assert client.get(URL).json() == [response.json()]
    assert client.get(URL + "/unread-count").json() == {"unread_count": 0}
    assert session.get(Notification, other_id).read_at is None


@pytest.mark.parametrize("value", ["bad", "0", "-1", str(2**63)])
def test_invalid_notification_ids_are_422(client, users, value):
    assert client.post(f"{URL}/{value}/read").status_code == 422
