"""Exercise deletion serialization with independent committed PostgreSQL sessions."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.auth.sessions import start_session, user_for_token
from app.db import engine
from app.db.models import Base, DeletionRequest, Notification, User
from app.deletion import (
    DeletionRateLimited, DeletionTokenCodec, InvalidDeletionToken,
    confirm_and_delete, create_deletion_request,
)


@pytest.fixture
def isolated_sessions():
    if engine.dialect.name != "postgresql":
        pytest.skip("requires PostgreSQL")
    schema = "test_privacy_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(isolated)
        yield sessionmaker(bind=isolated, expire_on_commit=False)
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


def test_concurrent_requests_issue_one_challenge_and_enforce_cooldown(isolated_sessions):
    factory = isolated_sessions
    codec = DeletionTokenCodec(b"ft57-concurrency-isolated-signing-secret")
    with factory.begin() as session:
        user = User(email="concurrent@example.test", password_hash="unused")
        session.add(user)
        session.flush()
        user_id = user.id

    barrier = threading.Barrier(2)

    def request():
        barrier.wait(timeout=5)
        try:
            with factory.begin() as session:
                token, _, _ = create_deletion_request(session, user_id, codec)
            return "issued", token
        except DeletionRateLimited:
            return "limited", None

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(lambda _: request(), range(2)))

    assert sorted(outcome for outcome, _ in outcomes) == ["issued", "limited"]
    with factory() as session:
        stored = session.get(DeletionRequest, user_id)
        assert stored is not None
        assert len(stored.token_hash) == 64


def test_concurrent_confirmations_delete_once_and_revoke_sessions(isolated_sessions):
    factory = isolated_sessions
    codec = DeletionTokenCodec(b"ft57-concurrency-isolated-signing-secret")
    with factory.begin() as session:
        user = User(email="concurrent@example.test", password_hash="unused")
        session.add(user)
        session.flush()
        user_id = user.id
        session_token = start_session(session, user)
        deletion_token, _, _ = create_deletion_request(session, user_id, codec)

    barrier = threading.Barrier(2)

    def confirm():
        barrier.wait(timeout=5)
        try:
            with factory.begin() as session:
                confirm_and_delete(session, user_id, deletion_token, codec)
            return "deleted"
        except InvalidDeletionToken:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(lambda _: confirm(), range(2)))

    assert sorted(outcomes) == ["deleted", "rejected"]
    with factory() as session:
        assert session.scalar(select(User).where(User.id == user_id)) is None
        assert session.get(DeletionRequest, user_id) is None
        assert user_for_token(session, session_token) is None


def test_reciprocal_notifications_do_not_deadlock_concurrent_deletions(isolated_sessions):
    factory = isolated_sessions
    codec = DeletionTokenCodec(b"ft57-concurrency-isolated-signing-secret")
    with factory.begin() as session:
        users = [
            User(email="first@example.test", password_hash="unused"),
            User(email="second@example.test", password_hash="unused"),
        ]
        session.add_all(users)
        session.flush()
        first_id, second_id = (user.id for user in users)
        session.add_all([
            Notification(recipient_id=first_id, actor_id=second_id, event_type="comment.created", message="Second", event_key="second:1"),
            Notification(recipient_id=second_id, actor_id=first_id, event_type="comment.created", message="First", event_key="first:1"),
        ])
        tokens = {
            user.id: create_deletion_request(session, user.id, codec)[0]
            for user in users
        }

    barrier = threading.Barrier(2)

    def confirm(user_id):
        barrier.wait(timeout=5)
        with factory.begin() as session:
            confirm_and_delete(session, user_id, tokens[user_id], codec)

    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(confirm, [first_id, second_id]))

    with factory() as session:
        assert session.get(User, first_id) is None
        assert session.get(User, second_id) is None
        assert session.scalar(select(Notification).where(Notification.recipient_id.in_([first_id, second_id]))) is None
