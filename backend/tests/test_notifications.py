"""Notification persistence and constraints, verified against real Postgres."""

import datetime

import pytest
from sqlalchemy import BigInteger, delete, inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.models import Notification, User


@pytest.fixture
def users(session):
    recipient = User(email="recipient@myplaylist.test", password_hash="hash")
    actor = User(email="actor@myplaylist.test", password_hash="hash")
    session.add_all([recipient, actor])
    session.flush()
    return recipient, actor


@pytest.fixture
def notification(session, users):
    recipient, actor = users
    notification = Notification(
        recipient=recipient, actor=actor, event_type="friend_request", message="A new friend request.",
        event_key="friend-request:1",
    )
    session.add(notification)
    session.flush()
    return notification


def test_relationships_distinguish_recipient_from_actor(session, users, notification):
    recipient, actor = users
    notification_id = notification.id
    session.expire_all()

    stored = session.get(Notification, notification_id)

    assert stored.recipient is recipient
    assert stored.actor is actor
    assert stored.event_type == "friend_request"
    assert stored.message == "A new friend request."
    assert recipient.received_notifications == [stored]
    assert actor.received_notifications == []


def test_plain_sql_insert_gets_timestamp_and_nullable_defaults(session, users):
    recipient, _ = users
    row = session.execute(
        text(
            "INSERT INTO notifications (recipient_id, event_type, message, event_key) "
            "VALUES (:recipient_id, 'system', 'Welcome.', 'welcome:1') "
            "RETURNING id, actor_id, created_at, read_at"
        ),
        {"recipient_id": recipient.id},
    ).one()

    assert isinstance(row.id, int)
    assert row.actor_id is None
    assert row.created_at.utcoffset() is not None
    assert row.read_at is None
    assert session.get(Notification, row.id).actor is None


def test_read_timestamp_round_trips_with_timezone(session, notification):
    read_at = datetime.datetime(2026, 11, 22, 15, 30, tzinfo=datetime.timezone(datetime.timedelta(hours=2)))
    notification.read_at = read_at
    session.flush()
    session.refresh(notification)

    assert notification.created_at.utcoffset() is not None
    assert notification.read_at.utcoffset() is not None
    assert notification.read_at == read_at


@pytest.mark.parametrize("field", ["recipient_id", "event_type", "message", "event_key", "created_at"])
def test_required_fields_reject_null(session, users, field):
    recipient, _ = users
    values = {"recipient_id": recipient.id, "event_type": "system", "message": "Welcome.", "event_key": "welcome:1"}
    values[field] = None

    # A Core INSERT sends explicit NULL even for the server-default column.
    with pytest.raises(IntegrityError) as error:
        session.execute(Notification.__table__.insert().values(**values))

    assert error.value.orig.pgcode == "23502"  # not_null_violation
    assert error.value.orig.diag.column_name == field


@pytest.mark.parametrize("field", ["recipient_id", "actor_id"])
def test_foreign_keys_reject_unknown_users(session, users, field):
    recipient, actor = users
    values = {"recipient_id": recipient.id, "actor_id": actor.id, "event_type": "friend_request", "message": "Hello.", "event_key": "friend-request:1"}
    values[field] = -1
    session.add(Notification(**values))

    with pytest.raises(IntegrityError) as error:
        session.flush()

    assert error.value.orig.pgcode == "23503"  # foreign_key_violation


@pytest.mark.parametrize("via_orm", [False, True], ids=["database", "orm"])
def test_deleting_recipient_deletes_notifications(session, users, notification, via_orm):
    recipient, actor = users
    notification_id, actor_id = notification.id, actor.id
    if via_orm:
        assert recipient.received_notifications == [notification]
        session.delete(recipient)
        session.flush()
    else:
        session.execute(delete(User).where(User.id == recipient.id))
    session.expire_all()

    assert session.get(Notification, notification_id) is None
    assert session.get(User, actor_id) is not None


@pytest.mark.parametrize("via_orm", [False, True], ids=["database", "orm"])
def test_deleting_actor_preserves_notification_with_null_actor(session, users, notification, via_orm):
    recipient, actor = users
    notification_id, recipient_id = notification.id, recipient.id
    if via_orm:
        session.delete(actor)
        session.flush()
    else:
        session.execute(delete(User).where(User.id == actor.id))
    session.expire_all()

    stored = session.get(Notification, notification_id)
    assert stored is not None
    assert stored.actor_id is None
    assert stored.actor is None
    assert stored.recipient_id == recipient_id
    assert stored.message == "A new friend request."


def test_migrated_schema_has_bigint_key_timezone_columns_and_one_composite_index(session):
    schema = inspect(session.connection())
    columns = {column["name"]: column for column in schema.get_columns("notifications")}
    assert isinstance(columns["id"]["type"], BigInteger)
    assert schema.get_pk_constraint("notifications")["constrained_columns"] == ["id"]
    assert columns["created_at"]["type"].timezone
    assert columns["read_at"]["type"].timezone
    assert not columns["event_key"]["nullable"]
    assert columns["event_key"]["type"].length == 255
    assert {constraint["name"]: constraint["column_names"] for constraint in schema.get_unique_constraints("notifications")} == {
        "uq_notifications_recipient_event_key": ["recipient_id", "event_key"],
    }
    indexes = [index for index in schema.get_indexes("notifications") if not index.get("duplicates_constraint")]
    assert len(indexes) == 1
    assert indexes[0]["column_names"] == ["recipient_id", "created_at"]
    assert not indexes[0]["unique"]
