"""Presence authorization uses the real ORM query on isolated SQLite tables.

Explicit IDs avoid SQLite's BIGINT autoincrement difference. Deterministic
least/greatest functions support the PostgreSQL unordered-pair expression index
without changing shared model metadata or dropping mapped timestamp columns.
These tests verify queries, not PostgreSQL migration compatibility.
"""

import asyncio
<<<<<<< HEAD
import datetime
import logging
from unittest.mock import AsyncMock, MagicMock, Mock, call

import pytest
from fastapi import WebSocket, WebSocketDisconnect
=======
import logging
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import WebSocket
>>>>>>> 9bb19c2 (feat(websocket): add friendship-based presence notifications)
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Friendship, User
<<<<<<< HEAD
from app.realtime.manager import ConnectionManager
from realtime_helpers import deliver_to_all
import app.realtime.manager as realtime_manager
import app.realtime.presence as presence


async def flush_presence(manager):
    """Drain queued work without tearing down the unit test's connections."""
    manager.start()
    try:
        await asyncio.wait_for(manager.presence_queue.join(), timeout=1)
    finally:
        manager.presence_worker.cancel()
        await asyncio.gather(manager.presence_worker, return_exceptions=True)


@pytest.fixture(autouse=True)
def ready_connections(monkeypatch):
    monkeypatch.setattr(ConnectionManager, "check_session", AsyncMock(return_value=True))
    # Query/unit tests begin with initialized sockets. Dispatcher tests cover
    # the real registration -> snapshot -> live delivery sequence.
    connect = ConnectionManager.connect

    async def ready_connect(manager, socket, user_id):
        result = await connect(manager, socket, user_id)
        manager.initializing.discard(socket)
        manager.initialization_admissions.pop(socket, None)
        return result

    monkeypatch.setattr(ConnectionManager, "connect", ready_connect)


=======
from app.main import ConnectionManager
import app.realtime.presence as presence


>>>>>>> 9bb19c2 (feat(websocket): add friendship-based presence notifications)
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
<<<<<<< HEAD
        assert sorted([friend.id for friend in presence.list_friends(session, user_id)]) == expected
=======
        assert sorted(presence.get_presence_recipients(session, user_id)) == expected
>>>>>>> 9bb19c2 (feat(websocket): add friendship-based presence notifications)


@pytest.mark.parametrize("user_id", [4, 5, 6, 7, 8, 9, 12, 999], ids=[
    "pending-outgoing", "pending-incoming", "declined-outgoing", "declined-incoming",
    "blocked-outgoing", "blocked-incoming", "no-relationships", "unknown-user",
])
def test_users_without_accepted_friends_have_no_recipients(presence_database, user_id):
    with presence_database() as session:
<<<<<<< HEAD
        assert [friend.id for friend in presence.list_friends(session, user_id)] == []
=======
        assert presence.get_presence_recipients(session, user_id) == []
>>>>>>> 9bb19c2 (feat(websocket): add friendship-based presence notifications)


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
<<<<<<< HEAD


@pytest.mark.anyio
@pytest.mark.parametrize("online_ids, expected", [
    ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], [2, 3]),
    ([2, 4, 5, 6, 7, 8, 9, 10, 11, 12], [2]),
    ([3, 4, 5, 6, 7, 8, 9, 10, 11, 12], [3]),
    ([4, 5, 6, 7, 8, 9, 10, 11, 12], []),
    ([], []),
], ids=["both-directions", "incoming-offline", "outgoing-offline",
        "only-nonfriends-online", "nobody-online"])
async def test_snapshot_contains_only_online_accepted_friends(
    presence_database, online_ids, expected,
):
    manager = ConnectionManager()
    observers = [MagicMock(spec=WebSocket) for _ in online_ids]
    for user_id, socket in zip(online_ids, observers):
        await manager.connect(socket, user_id)
    first_tab, new_tab = MagicMock(spec=WebSocket), MagicMock(spec=WebSocket)
    await manager.connect(first_tab, 1)
    await manager.connect(new_tab, 1)

    # Real SQL filtering and threadpool lookup; no mocked friendship results.
    await presence.send_presence_snapshot(manager, new_tab, 1)

    new_tab.send_json.assert_awaited_once()
    event = new_tab.send_json.await_args.args[0]
    assert isinstance(event["data"]["online_user_ids"], list)
    assert event == {
        "type": "presence_snapshot",
        "data": {"online_user_ids": event["data"]["online_user_ids"]},
    }
    assert sorted(event["data"]["online_user_ids"]) == expected
    first_tab.send_json.assert_not_awaited()
    for socket in observers:
        socket.send_json.assert_not_awaited()


@pytest.mark.anyio
async def test_snapshot_for_user_without_friendships_is_empty(presence_database):
    manager = ConnectionManager()
    for user_id in range(1, 12):
        await manager.connect(MagicMock(spec=WebSocket), user_id)
    socket = MagicMock(spec=WebSocket)
    await manager.connect(socket, 12)

    await presence.send_presence_snapshot(manager, socket, 12)

    socket.send_json.assert_awaited_once_with({
        "type": "presence_snapshot", "data": {"online_user_ids": []},
    })


@pytest.mark.anyio
async def test_get_online_friends_filters_offline_ids_without_mutating_input():
    manager = ConnectionManager()
    for user_id in (2, 2, 3, 99):
        await manager.connect(MagicMock(spec=WebSocket), user_id)
    friend_ids = [1, 3, 2, 4]

    assert presence.get_online_friends(manager, friend_ids) == [3, 2]
    assert friend_ids == [1, 3, 2, 4]
    assert presence.get_online_friends(manager, []) == []


@pytest.mark.anyio
@pytest.mark.parametrize("failure_at, error", [
    ("lookup", RuntimeError("snapshot lookup failed")),
    ("send", OSError("snapshot transport failed")),
    ("send", WebSocketDisconnect(code=1006)),
])
async def test_snapshot_safe_wrapper_logs_and_suppresses_errors(
    monkeypatch, caplog, failure_at, error,
):
    manager = ConnectionManager()
    socket = MagicMock(spec=WebSocket)
    await manager.connect(socket, 1)
    friend = MagicMock(spec=WebSocket)
    await manager.connect(friend, 2)
    lookup = Mock(return_value=[2], side_effect=error if failure_at == "lookup" else None)
    monkeypatch.setattr(presence, "find_presence_recipients", lookup)
    if failure_at == "send":
        socket.send_json.side_effect = error

    with caplog.at_level(logging.ERROR, logger=presence.__name__):
        await presence.send_presence_snapshot_safely(manager, socket, 1)

    lookup.assert_called_once_with(1)
    if failure_at == "send":
        socket.send_json.assert_awaited_once_with({
            "type": "presence_snapshot", "data": {"online_user_ids": [2]},
        })
    else:
        socket.send_json.assert_not_awaited()
    # Both lookup and transport failures now close initialization. Cleanup
    # records the transition but never delivers recursively.
    assert manager.active_connections == {2: {friend}}
    socket.close.assert_awaited_once_with(code=1011)
    assert 1 in manager.pending_presence
    friend.send_json.assert_not_awaited()
    records = [record for record in caplog.records if record.name == presence.__name__]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].getMessage() == "Failed to send presence snapshot for user 1"
    assert records[0].exc_info[1] is error


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [OSError, WebSocketDisconnect])
@pytest.mark.parametrize("healthy_tab", [False, True], ids=["last-tab", "healthy-sibling"])
async def test_failed_snapshot_send_removes_dead_socket(
    presence_database, monkeypatch, failure, healthy_tab,
):
    manager = ConnectionManager()
    broken, sibling = MagicMock(spec=WebSocket), MagicMock(spec=WebSocket)
    friend = MagicMock(spec=WebSocket)
    await manager.connect(friend, 2)
    await manager.connect(broken, 1)
    if healthy_tab:
        await manager.connect(sibling, 1)
    notify = AsyncMock(wraps=presence.notify_presence_safely)
    monkeypatch.setattr(realtime_manager, "notify_presence_safely", notify)
    await flush_presence(manager)
    notify.reset_mock()
    friend.send_json.reset_mock()
    sibling.send_json.reset_mock()
    broken.send_json.reset_mock()
    broken.send_json.side_effect = failure()

    await presence.send_presence_snapshot_safely(manager, broken, 1)
    await flush_presence(manager)

    broken.send_json.assert_awaited_once_with({
        "type": "presence_snapshot", "data": {"online_user_ids": [2]},
    })
    expected_connections = {2: {friend}}
    if healthy_tab:
        expected_connections[1] = {sibling}
        notify.assert_not_awaited()
        friend.send_json.assert_not_awaited()
    else:
        notify.assert_awaited_once_with(manager, 1, False)
        friend.send_json.assert_awaited_once_with({
            "type": "presence", "data": {"user_id": 1, "online": False},
        })
    assert manager.active_connections == expected_connections
    sibling.send_json.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("delivery", ["server_fanout", "send_to_user"])
@pytest.mark.parametrize("healthy_tab", [False, True], ids=["last-tab", "healthy-sibling"])
async def test_failed_send_cleanup_delivers_offline_presence_to_friends(
    presence_database, monkeypatch, delivery, healthy_tab,
):
    manager = ConnectionManager()
    broken, sibling, friend, outsider = [MagicMock(spec=WebSocket) for _ in range(4)]
    for user_id, socket in ((1, broken), (2, friend), (12, outsider)):
        await manager.connect(socket, user_id)
    if healthy_tab:
        await manager.connect(sibling, 1)
    notify = AsyncMock(wraps=presence.notify_presence_safely)
    monkeypatch.setattr(realtime_manager, "notify_presence_safely", notify)
    await flush_presence(manager)
    notify.reset_mock()
    for socket in (broken, sibling, friend, outsider):
        socket.send_json.reset_mock()
    broken.send_json.side_effect = OSError("connection lost")
    message = {"type": "message", "data": {"text": "detect failure"}}

    if delivery == "server_fanout":
        await deliver_to_all(manager, "detect failure")
    else:
        await manager.send_to_user(1, message)

    await flush_presence(manager)
    broken.send_json.assert_awaited_once_with(message)
    assert manager.active_connections.get(1, set()) == ({sibling} if healthy_tab else set())
    expected_friend_events = [message] if delivery == "server_fanout" else []
    if not healthy_tab:
        expected_friend_events.append({"type": "presence", "data": {"user_id": 1, "online": False}})
    assert [args.args[0] for args in friend.send_json.await_args_list] == expected_friend_events
    assert [args.args[0] for args in outsider.send_json.await_args_list] == (
        [message] if delivery == "server_fanout" else []
    )
    if healthy_tab:
        notify.assert_not_awaited()
        sibling.send_json.assert_awaited_once_with(message)
    else:
        notify.assert_awaited_once_with(manager, 1, False)


@pytest.mark.anyio
async def test_deleted_friends_are_excluded_from_snapshots_and_delivery(presence_database):
    with presence_database.begin() as session:
        session.get(User, 2).deleted_at = datetime.datetime.now(datetime.timezone.utc)
    assert presence.find_presence_recipients(1) == [3]
    manager = ConnectionManager()
    subject, deleted, friend = [MagicMock(spec=WebSocket) for _ in range(3)]
    for user_id, socket in ((1, subject), (2, deleted), (3, friend)):
        await manager.connect(socket, user_id)
    await presence.send_presence_snapshot(manager, subject, 1)
    subject.send_json.assert_awaited_once_with({
        "type": "presence_snapshot", "data": {"online_user_ids": [3]},
    })
    await presence.notify_presence(manager, 1, True)
    deleted.send_json.assert_not_awaited()
    friend.send_json.assert_awaited_once_with({
        "type": "presence", "data": {"user_id": 1, "online": True},
    })
=======
>>>>>>> 9bb19c2 (feat(websocket): add friendship-based presence notifications)
