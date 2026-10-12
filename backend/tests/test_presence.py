"""Presence authorization uses the real ORM query on isolated SQLite tables.

Explicit IDs avoid SQLite's BIGINT autoincrement difference. Deterministic
least/greatest functions support the PostgreSQL unordered-pair expression index
without changing shared model metadata or dropping mapped timestamp columns.
These tests verify queries, not PostgreSQL migration compatibility.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import WebSocket
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Friendship, User
from app.main import ConnectionManager
import app.realtime.presence as presence


@pytest.fixture
def presence_database(tmp_path, monkeypatch):
    # A file lets the real threadpool lookup open its own SQLite connection.
    engine = create_engine(f"sqlite:///{tmp_path / 'presence.sqlite'}")

    @event.listens_for(engine, "connect")
    def sqlite_functions(connection, _record):
        connection.create_function("least", 2, min, deterministic=True)
        connection.create_function("greatest", 2, max, deterministic=True)
        connection.execute("PRAGMA foreign_keys=ON")

    factory = sessionmaker(bind=engine)
    try:
        Base.metadata.create_all(engine, tables=[User.__table__, Friendship.__table__])
        with factory.begin() as session:
            session.add_all([
                User(id=user_id, email=f"user{user_id}@example.test", password_hash="unused")
                for user_id in range(1, 13)
            ])
            session.flush()
            session.add_all([
                Friendship(id=row_id, requester_id=requester, addressee_id=addressee, status=status)
                for row_id, (requester, addressee, status) in enumerate([
                    (1, 2, "accepted"), (3, 1, "accepted"),
                    (1, 4, "pending"), (5, 1, "pending"),
                    (1, 6, "declined"), (7, 1, "declined"),
                    (1, 8, "blocked"), (9, 1, "blocked"),
                    (10, 11, "accepted"),
                ], start=1)
            ])
        monkeypatch.setattr(presence, "SessionLocal", factory)
        yield factory
    finally:
        engine.dispose()


@pytest.mark.parametrize("user_id, expected", [(1, [2, 3]), (2, [1]), (3, [1])])
def test_only_accepted_friends_in_either_direction_are_recipients(
    presence_database, user_id, expected,
):
    with presence_database() as session:
        assert sorted(presence.get_presence_recipients(session, user_id)) == expected


@pytest.mark.parametrize("user_id", [4, 5, 6, 7, 8, 9, 12, 999], ids=[
    "pending-outgoing", "pending-incoming", "declined-outgoing", "declined-incoming",
    "blocked-outgoing", "blocked-incoming", "no-relationships", "unknown-user",
])
def test_users_without_accepted_friends_have_no_recipients(presence_database, user_id):
    with presence_database() as session:
        assert presence.get_presence_recipients(session, user_id) == []


def test_find_presence_recipients_uses_and_closes_its_own_session(presence_database, monkeypatch):
    session = presence_database()
    close = Mock(wraps=session.close)
    monkeypatch.setattr(session, "close", close)
    factory = Mock(return_value=session)
    monkeypatch.setattr(presence, "SessionLocal", factory)

    assert sorted(presence.find_presence_recipients(1)) == [2, 3]

    factory.assert_called_once_with()
    close.assert_called_once_with()


@pytest.mark.anyio
@pytest.mark.parametrize("online", [True, False], ids=["online", "offline"])
async def test_presence_event_reaches_only_accepted_friends_on_all_their_tabs(
    presence_database, online,
):
    manager = ConnectionManager()
    sockets = {}
    # Every excluded relationship and unrelated user is actively connected.
    for user_id in range(2, 13):
        sockets[user_id] = MagicMock(spec=WebSocket)
        await manager.connect(sockets[user_id], user_id)
    extra_tab = MagicMock(spec=WebSocket)
    await manager.connect(extra_tab, 2)
    subject = MagicMock(spec=WebSocket)
    if online:
        await manager.connect(subject, 1)

    # Exercise the real threadpool, SQL lookup, and manager delivery together.
    await presence.notify_presence(manager, 1, online)

    expected = {"type": "presence", "data": {"user_id": 1, "online": online}}
    for user_id, socket in sockets.items():
        if user_id in (2, 3):
            socket.send_json.assert_awaited_once_with(expected)
        else:
            socket.send_json.assert_not_awaited()
    extra_tab.send_json.assert_awaited_once_with(expected)
    subject.send_json.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("online", [True, False])
async def test_no_recipients_means_no_delivery(presence_database, monkeypatch, online):
    manager = ConnectionManager()
    if online:
        await manager.connect(MagicMock(spec=WebSocket), 12)
    send = AsyncMock(wraps=manager.send_to_user)
    monkeypatch.setattr(manager, "send_to_user", send)

    await presence.notify_presence(manager, 12, online)

    send.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("online", [True, False], ids=["disconnected-during-lookup", "reconnected-during-lookup"])
async def test_stale_notification_is_discarded_when_state_changes_during_lookup(monkeypatch, online):
    manager = ConnectionManager()
    subject, friend = MagicMock(spec=WebSocket), MagicMock(spec=WebSocket)
    await manager.connect(friend, 2)
    if online:
        await manager.connect(subject, 1)
    lookup_started, finish_lookup = asyncio.Event(), asyncio.Event()

    async def delayed_lookup(function, user_id):
        assert function is presence.find_presence_recipients
        assert user_id == 1
        lookup_started.set()
        await finish_lookup.wait()
        return [2]

    monkeypatch.setattr(presence, "run_in_threadpool", delayed_lookup)
    notification = asyncio.create_task(presence.notify_presence(manager, 1, online))
    try:
        await asyncio.wait_for(lookup_started.wait(), timeout=1)
        if online:
            assert manager.disconnect(subject, 1) is True
        else:
            assert await manager.connect(subject, 1) is True
        finish_lookup.set()
        await asyncio.wait_for(notification, timeout=1)
    finally:
        if not notification.done():
            notification.cancel()
        await asyncio.gather(notification, return_exceptions=True)

    friend.send_json.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("online", [True, False])
@pytest.mark.parametrize("failure_at", ["lookup", "delivery"])
async def test_notify_presence_safely_logs_and_suppresses_errors(
    monkeypatch, caplog, online, failure_at,
):
    manager = ConnectionManager()
    if online:
        await manager.connect(MagicMock(spec=WebSocket), 1)
    error = RuntimeError(f"presence {failure_at} failed")
    lookup = Mock(return_value=[2], side_effect=error if failure_at == "lookup" else None)
    delivery = AsyncMock(side_effect=error if failure_at == "delivery" else None)
    monkeypatch.setattr(presence, "find_presence_recipients", lookup)
    monkeypatch.setattr(manager, "send_to_user", delivery)

    with caplog.at_level(logging.ERROR, logger=presence.__name__):
        await presence.notify_presence_safely(manager, 1, online)

    lookup.assert_called_once_with(1)
    if failure_at == "delivery":
        delivery.assert_awaited_once_with(
            2, {"type": "presence", "data": {"user_id": 1, "online": online}},
        )
    else:
        delivery.assert_not_awaited()
    records = [record for record in caplog.records if record.name == presence.__name__]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].getMessage() == f"Failed to notify presence for user 1 (online={online})"
    assert records[0].exc_info[1] is error
