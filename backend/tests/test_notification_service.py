"""Notification transaction ownership and retry semantics on real PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.crud.notification import create_notification, list_notifications, mark_as_read, unread_count
from app.db import engine
from app.db.models import Base, Friendship, Notification, Top10Reaction, User
from app.crud.reaction import create_reaction


@pytest.fixture
def recipient(session):
    user = User(email="recipient@notification.test", password_hash="hash")
    session.add(user)
    session.flush()
    session.commit()
    return user


def create(session, recipient_id, key="event:1"):
    return create_notification(session, recipient_id, event_key=key, event_type="system", message="Hello.")


def test_create_rolls_back_with_the_callers_other_changes(session, recipient):
    recipient_id = recipient.id
    recipient.is_verified = True
    notification = create(session, recipient_id)
    notification_id = notification.id
    assert unread_count(session, recipient_id) == 1

    session.rollback()

    assert session.get(Notification, notification_id) is None
    assert not session.get(User, recipient_id).is_verified
    assert unread_count(session, recipient_id) == 0
    assert create(session, recipient_id).id != notification_id  # rollback did not consume the event key


def test_mark_read_rolls_back_with_the_caller(session, recipient):
    notification = create(session, recipient.id)
    notification_id = notification.id
    session.commit()

    mark_as_read(session, recipient.id, notification_id)
    assert unread_count(session, recipient.id) == 0
    session.rollback()

    assert session.get(Notification, notification_id).read_at is None
    assert unread_count(session, recipient.id) == 1


def test_retry_after_commit_preserves_original_message_and_read_status(session, recipient):
    first = create(session, recipient.id)
    session.commit()
    read_at = mark_as_read(session, recipient.id, first.id).read_at
    session.commit()

    retry = create_notification(session, recipient.id, event_key="event:1", event_type="changed", message="Changed.")

    assert retry.id == first.id
    assert retry.message == "Hello."
    assert retry.event_type == "system"
    assert retry.read_at == read_at
    assert len(list_notifications(session, recipient.id)) == 1


def test_keys_are_scoped_to_recipient_and_distinct_events_are_not_collapsed(session, recipient):
    other = User(email="other@notification.test", password_hash="hash")
    session.add(other)
    session.flush()
    first = create(session, recipient.id)
    retry = create(session, recipient.id)
    different_event = create(session, recipient.id, "event:2")
    different_recipient = create(session, other.id)

    assert first.id == retry.id
    assert len({first.id, different_event.id, different_recipient.id}) == 3
    assert unread_count(session, recipient.id) == 2
    assert unread_count(session, other.id) == 1


def test_unique_constraint_rejects_duplicate_keys_outside_service(session, recipient):
    create(session, recipient.id)
    session.add(Notification(recipient_id=recipient.id, event_key="event:1", event_type="system", message="Duplicate"))
    with pytest.raises(IntegrityError) as error:
        session.flush()
    assert error.value.orig.diag.constraint_name == "uq_notifications_recipient_event_key"


@pytest.mark.parametrize("key", ["", "   ", "x" * 256])
def test_creation_requires_a_bounded_nonempty_event_key(session, recipient, key):
    with pytest.raises(ValueError):
        create(session, recipient.id, key)
    assert unread_count(session, recipient.id) == 0


@pytest.mark.parametrize("limit,offset", [(0, 0), (-1, 0), (101, 0), (20, -1), (20, 10001)])
def test_service_enforces_pagination_bounds(session, recipient, limit, offset):
    with pytest.raises(ValueError):
        list_notifications(session, recipient.id, limit=limit, offset=offset)


def test_service_does_not_allow_another_recipient_to_mark_read(session, recipient):
    notification = create(session, recipient.id)
    with pytest.raises(HTTPException) as error:
        mark_as_read(session, recipient.id + 1, notification.id)
    assert error.value.status_code == 404
    assert notification.read_at is None


def test_concurrent_creation_retries_produce_one_notification():
    # Committed, independent connections are needed to exercise uniqueness races.
    # As in the realtime integration tests, all data lives in a temporary schema.
    schema = "test_notification_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    factory = sessionmaker(bind=isolated)
    try:
        Base.metadata.create_all(isolated)
        with factory.begin() as session:
            user = User(email="concurrent@notification.test", password_hash="hash")
            session.add(user)
            session.flush()
            recipient_id = user.id
        ready = Barrier(2)

        def worker():
            with factory.begin() as session:
                # Fail promptly if a regression causes database lock contention.
                session.execute(text("SET LOCAL statement_timeout = '5s'"))
                ready.wait(timeout=5)
                return create(session, recipient_id).id

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(worker) for _ in range(2)]
            ids = [result.result(timeout=10) for result in results]
        assert ids[0] == ids[1]
        with factory() as session:
            assert session.scalars(select(Notification)).one().id == ids[0]
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


def test_concurrent_reaction_creation_retry_keeps_one_reaction_and_notification():
    schema = "test_reaction_retry_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    ready = Barrier(2)

    class RacingSession(Session):
        def flush(self, objects=None):
            if any(isinstance(row, Top10Reaction) for row in self.new):
                ready.wait(timeout=5)
            return super().flush(objects)

    factory = sessionmaker(bind=isolated, class_=RacingSession)
    try:
        Base.metadata.create_all(isolated)
        with factory.begin() as session:
            owner = User(email="owner@reaction-retry.test", password_hash="hash")
            actor = User(email="actor@reaction-retry.test", password_hash="hash")
            session.add_all([owner, actor])
            session.flush()
            owner_id, actor_id = owner.id, actor.id
            session.add(Friendship(requester_id=actor_id, addressee_id=owner_id, status="accepted"))

        def worker():
            with factory.begin() as session:
                session.execute(text("SET LOCAL statement_timeout = '5s'"))
                return create_reaction(owner_id, "like", session, session.get(User, actor_id)).id

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            ids = [future.result(timeout=10) for future in futures]

        assert ids[0] == ids[1]
        with factory() as session:
            assert session.scalars(select(Top10Reaction)).one().id == ids[0]
            notification = session.scalars(select(Notification)).one()
            assert notification.event_type == "reaction.created"
            assert notification.recipient_id == owner_id
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
