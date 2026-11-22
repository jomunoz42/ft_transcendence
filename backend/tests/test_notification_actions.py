"""Existing social actions persist recipient-safe notifications atomically."""

import datetime
from unittest.mock import Mock

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.sessions import start_session
from app.crud.comment import create_comment, update_comment, delete_comment
from app.crud.reaction import create_reaction, delete_reaction
from app.db.models import Block, Friendship, Notification, Profile, Top10Comment, Top10Reaction, User
from app.main import app
from app.notifications import record_action
from app.realtime.notifications import get_notifications_notifier
from app.routes.v1.friendships import send_request


@pytest.fixture
def social(session, client):
    users = [User(email=f"social{i}@example.test", password_hash="hash", profile=Profile(display_name=f"User {i}")) for i in range(3)]
    session.add_all(users)
    session.flush()
    tokens = [start_session(session, user) for user in users]
    session.commit()
    client.cookies.set(SESSION_COOKIE_NAME, tokens[0])
    return users, tokens


@pytest.fixture
def delivered():
    events = []
    app.dependency_overrides[get_notifications_notifier] = lambda: events.extend
    try:
        yield events
    finally:
        app.dependency_overrides.pop(get_notifications_notifier, None)


def rows(session):
    return list(session.scalars(select(Notification).order_by(Notification.id)))


def befriend(session, users):
    session.add(Friendship(requester_id=users[0].id, addressee_id=users[1].id, status="accepted"))
    session.commit()


@pytest.mark.parametrize("action,status,actor,expected", [
    ("request", None, 0, "friend_request.created"),
    ("request", "pending", 1, "friend_request.accepted"),
    ("accept", "pending", 1, "friend_request.accepted"),
    ("decline", "pending", 1, "friend_request.declined"),
    ("cancel", "pending", 0, "friend_request.cancelled"),
    ("remove", "accepted", 0, "friendship.removed"),
])
def test_friendship_events_and_retries(session, client, social, delivered, action, status, actor, expected):
    users, tokens = social
    if status:
        session.add(Friendship(requester_id=users[0].id, addressee_id=users[1].id, status=status))
        session.commit()
    client.cookies.set(SESSION_COOKIE_NAME, tokens[actor])
    recipient = users[1 - actor]
    method = "delete" if action == "remove" else "post"
    path = f"/api/v1/friends/{recipient.id}" if action == "remove" else f"/api/v1/friends/{action}/{recipient.id}"
    assert getattr(client, method)(path).status_code == 200
    notifications = rows(session)
    assert len(notifications) == 1
    row = notifications[0]
    assert (row.event_type, row.recipient_id, row.actor_id) == (expected, recipient.id, users[actor].id)
    assert delivered == [(recipient.id, row.id)]

    assert getattr(client, method)(path).status_code in (200, 404)
    assert len(rows(session)) == 1
    assert delivered == [(recipient.id, row.id)]


def test_reopened_friend_requests_are_new_events(session, client, social, delivered):
    users, tokens = social
    for actor, action in [(0, "request"), (1, "decline"), (1, "request"), (0, "decline"), (0, "request")]:
        client.cookies.set(SESSION_COOKIE_NAME, tokens[actor])
        assert client.post(f"/api/v1/friends/{action}/{users[1 - actor].id}").status_code == 200
    notifications = rows(session)
    assert [row.event_type for row in notifications] == [
        "friend_request.created", "friend_request.declined", "friend_request.created",
        "friend_request.declined", "friend_request.created",
    ]
    assert len({row.event_key for row in notifications}) == 5


@pytest.mark.parametrize("latest", [False, True])
def test_comment_create_edit_delete_and_noops(session, client, social, delivered, latest):
    users, _ = social
    befriend(session, users)
    path = f"/api/v1/profiles/{users[1].id}/comments"
    response = client.post(path, json={"body": "private comment text"})
    assert response.status_code == 200
    comment_id = session.scalar(select(Top10Comment.id))
    edit = path + ("/latest" if latest else f"/{comment_id}")
    for body in ["private comment text", "edited", "edited", "private comment text", "edited"]:
        assert client.post(edit, json={"body": body}).status_code == 200
    assert client.delete(f"{path}/{comment_id}").status_code == 200
    assert client.delete(f"{path}/{comment_id}").status_code == 404
    notifications = rows(session)
    assert [row.event_type for row in notifications] == ["comment.created"] + ["comment.updated"] * 3 + ["comment.deleted"]
    assert len({row.event_key for row in notifications}) == 5
    assert all(row.recipient_id == users[1].id and row.actor_id == users[0].id for row in notifications)
    assert all("private comment text" not in row.message and "edited" not in row.message for row in notifications)
    assert delivered == [(row.recipient_id, row.id) for row in notifications]


def test_distinct_comment_posts_remain_distinct_actions_but_replaying_one_event_is_deduplicated(session, client, social, delivered):
    users, _ = social
    befriend(session, users)
    path = f"/api/v1/profiles/{users[1].id}/comments"
    ids = []
    for _ in range(2):
        assert client.post(path, json={"body": "Same text"}).status_code == 200
        ids.append(session.scalar(select(Top10Comment.id).order_by(Top10Comment.id.desc())))
    assert ids[0] != ids[1]
    events = []
    source = session.get(Top10Comment, ids[0])
    record_action(session, source, "comment.created", users[1].id, users[0].id, events)
    source.updated_at = source.updated_at.astimezone(datetime.timezone(datetime.timedelta(hours=2)))
    record_action(session, source, "comment.created", users[1].id, users[0].id, events)
    assert len(rows(session)) == 2
    assert events == []


def test_reaction_create_update_delete_and_noops(session, client, social, delivered):
    users, _ = social
    befriend(session, users)
    path = f"/api/v1/profiles/{users[1].id}/reactions"
    for value in ["like", "like", "dislike", "dislike", "like", "dislike"]:
        assert client.post(path, json={"reaction": value}).status_code == 200
    assert client.delete(path).status_code == 200
    assert client.delete(path).status_code == 404
    notifications = rows(session)
    assert [row.event_type for row in notifications] == ["reaction.created"] + ["reaction.updated"] * 3 + ["reaction.deleted"]
    assert len({row.event_key for row in notifications}) == 5
    assert delivered == [(users[1].id, row.id) for row in notifications]


def test_block_unblock_and_failed_actions_do_not_notify(session, client, social, delivered):
    users, _ = social
    befriend(session, users)
    assert client.post(f"/api/v1/friends/block/{users[1].id}").status_code == 200
    assert client.post(f"/api/v1/friends/request/{users[1].id}").status_code == 409
    assert client.post(f"/api/v1/profiles/{users[1].id}/comments", json={"body": "secret"}).status_code == 422
    assert client.post(f"/api/v1/profiles/{users[1].id}/reactions", json={"reaction": "like"}).status_code == 403
    assert client.post(f"/api/v1/friends/unblock/{users[1].id}").status_code == 200
    assert client.post(f"/api/v1/friends/request/{users[0].id}").status_code == 422
    assert rows(session) == []
    assert delivered == []


@pytest.mark.parametrize("blocked_by", [0, 1])
def test_existing_comment_delete_authorization_does_not_disclose_to_blocked_users(session, client, social, delivered, blocked_by):
    users, _ = social
    comment = Top10Comment(top10_owner_id=users[1].id, author_id=users[0].id, body="Old private text")
    session.add(comment)
    session.add(Block(blocker_id=users[blocked_by].id, blocked_id=users[1 - blocked_by].id))
    session.commit()
    assert client.delete(f"/api/v1/profiles/{users[1].id}/comments/{comment.id}").status_code == 200
    assert rows(session) == []
    assert delivered == []


def test_self_content_does_not_notify(session, social):
    users, _ = social
    events = []
    comment = create_comment(users[0].id, "Self", session, users[0], events)
    update_comment(comment.id, users[0].id, "Edited self", session, users[0], events)
    delete_comment(comment.id, users[0].id, session, users[0], events)
    assert rows(session) == []
    assert events == []


@pytest.mark.parametrize("action", ["friend", "comment", "reaction"])
def test_action_and_notification_roll_back_together(session, social, action):
    users, _ = social
    if action != "friend":
        befriend(session, users)
    events = []
    if action == "friend":
        source = send_request(session, users[0].id, users[1].id, events)
    elif action == "comment":
        source = create_comment(users[1].id, "Rollback", session, users[0], events)
    else:
        source = create_reaction(users[1].id, "like", session, users[0], events)
    source_id, model = source.id, type(source)
    assert len(rows(session)) == 1
    session.rollback()
    assert session.get(model, source_id) is None
    assert rows(session) == []


@pytest.mark.parametrize("action", ["friend", "comment", "reaction"])
def test_commit_failure_does_not_deliver(session, client, social, delivered, monkeypatch, action):
    users, _ = social
    if action != "friend":
        befriend(session, users)
    monkeypatch.setattr(session, "commit", Mock(side_effect=SQLAlchemyError("test commit failure")))
    path, body = {
        "friend": (f"/api/v1/friends/request/{users[1].id}", None),
        "comment": (f"/api/v1/profiles/{users[1].id}/comments", {"body": "Rollback"}),
        "reaction": (f"/api/v1/profiles/{users[1].id}/reactions", {"reaction": "like"}),
    }[action]
    with pytest.raises(SQLAlchemyError):
        client.post(path, json=body)
    assert delivered == []
    assert rows(session) == []


def test_notification_insert_failure_rolls_back_the_action(session, client, social, delivered, monkeypatch):
    import app.notifications as notifications
    users, _ = social
    befriend(session, users)
    monkeypatch.setattr(notifications, "create_notification", Mock(side_effect=SQLAlchemyError("notification failed")))
    with pytest.raises(SQLAlchemyError):
        client.post(f"/api/v1/profiles/{users[1].id}/comments", json={"body": "Rollback"})
    assert session.scalars(select(Top10Comment)).all() == []
    assert rows(session) == []
    assert delivered == []


@pytest.mark.parametrize("kind", ["comment", "reaction"])
@pytest.mark.parametrize("operation", ["update", "delete"])
def test_update_and_delete_rollback_restore_source_and_remove_new_notification(session, social, kind, operation):
    users, _ = social
    befriend(session, users)
    if kind == "comment":
        source = create_comment(users[1].id, "Original", session, users[0])
    else:
        source = create_reaction(users[1].id, "like", session, users[0])
    source_id, model = source.id, type(source)
    session.commit()
    if kind == "comment" and operation == "update":
        update_comment(source_id, users[1].id, "Updated", session, users[0])
    elif kind == "comment":
        delete_comment(source_id, users[1].id, session, users[0])
    elif operation == "update":
        create_reaction(users[1].id, "dislike", session, users[0])
    else:
        delete_reaction(users[1].id, session, users[0])
    assert len(rows(session)) == 2
    session.rollback()
    restored = session.get(model, source_id)
    assert restored is not None
    assert (restored.body if kind == "comment" else restored.reaction) == ("Original" if kind == "comment" else "like")
    assert [row.event_type for row in rows(session)] == [f"{kind}.created"]


def test_another_users_comment_cannot_be_changed_or_generate_events(session, client, social, delivered):
    users, tokens = social
    befriend(session, users)
    comment = create_comment(users[1].id, "Original", session, users[0])
    comment_id = comment.id
    session.commit()
    client.cookies.set(SESSION_COOKIE_NAME, tokens[2])
    path = f"/api/v1/profiles/{users[1].id}/comments/{comment_id}"
    assert client.post(path, json={"body": "Unauthorized"}).status_code == 404
    assert client.delete(path).status_code == 404
    assert session.get(Top10Comment, comment_id).body == "Original"
    assert len(rows(session)) == 1
    assert delivered == []
