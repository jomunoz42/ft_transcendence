"""Cancellation, admission and retry regressions through the real dispatcher."""

import asyncio
from unittest.mock import Mock

import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy.exc import OperationalError, ProgrammingError, TimeoutError as PoolTimeout

import app.main as main
import app.realtime.presence as presence
from test_presence_dispatcher import Socket, dispatcher, friendships, ready, settle

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("delivery", ["broadcast", "send_to_user"])
async def test_cancelled_lock_waiter_does_not_disconnect_active_writer(dispatcher, delivery):
    manager = dispatcher
    socket = Socket()
    await ready(manager, socket, 1)
    socket.send_json.reset_mock()
    writing, release, waiting = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def transport(event):
        if event["data"]["text"] == "first":
            writing.set()
            await release.wait()

    socket.send_json.side_effect = transport
    first = asyncio.create_task(manager.broadcast("first"))

    async def second_sender():
        waiting.set()
        if delivery == "broadcast":
            await manager.broadcast("cancelled")
        else:
            await manager.send_to_user(1, {"type": "message", "data": {"text": "cancelled"}})

    try:
        await asyncio.wait_for(writing.wait(), 1)
        second = asyncio.create_task(second_sender())
        await asyncio.wait_for(waiting.wait(), 1)
        assert not second.done()
        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second
        assert manager.active_connections == {1: {socket}}
        socket.close.assert_not_awaited()
        assert socket.events == [{"type": "message", "data": {"text": "first"}}]
    finally:
        release.set()
        await asyncio.wait_for(first, 1)
    await manager.broadcast("still healthy")
    assert socket.events[-1]["data"]["text"] == "still healthy"


@pytest.mark.parametrize("has_sibling", [False, True])
async def test_cancelled_transport_write_removes_only_affected_socket(
    dispatcher, friendships, has_sibling,
):
    manager = dispatcher
    observer, socket, sibling = Socket(), Socket(), Socket()
    friendships.update({1: [2], 2: [1]})
    await ready(manager, observer, 2)
    await ready(manager, socket, 1)
    if has_sibling:
        await ready(manager, sibling, 1)
    observer.send_json.reset_mock()
    writing, blocked = asyncio.Event(), asyncio.Event()

    async def transport(event):
        writing.set()
        await blocked.wait()

    socket.send_json.side_effect = transport
    sender = asyncio.create_task(manager.send_event(socket, 1, {"type": "message"}))
    await asyncio.wait_for(writing.wait(), 1)
    sender.cancel()
    with pytest.raises(asyncio.CancelledError):
        await sender
    await settle(manager)
    socket.close.assert_awaited_once_with(code=1011)
    assert socket not in manager.send_locks
    assert manager.active_connections.get(1, set()) == ({sibling} if has_sibling else set())
    assert observer.events == ([] if has_sibling else [
        {"type": "presence", "data": {"user_id": 1, "online": False}},
    ])
    if has_sibling:
        manager.disconnect(sibling, 1)
        await settle(manager)
        assert observer.events == [{"type": "presence", "data": {"user_id": 1, "online": False}}]


def database_error(kind, code=None, invalidated=False):
    original = Exception("database failure")
    original.pgcode = code
    return kind("query", {}, original, connection_invalidated=invalidated)


@pytest.mark.parametrize("error,retry", [
    (OSError("connection lost"), True),
    (TimeoutError(), True),
    (PoolTimeout("pool busy"), True),
    (database_error(OperationalError), True),
    (database_error(OperationalError, "08006"), True),
    (database_error(OperationalError, "40001"), True),
    (database_error(OperationalError, "40P01"), True),
    (database_error(OperationalError, "57014"), True),
    (database_error(OperationalError, "28P01"), False),
    (database_error(ProgrammingError, "42P01"), False),
    (RuntimeError("programming error"), False),
    (ValueError("invalid data"), False),
])
async def test_only_transient_presence_errors_request_retry(dispatcher, monkeypatch, error, retry):
    monkeypatch.setattr(presence, "find_presence_recipients", Mock(side_effect=error))
    result = await presence.notify_presence_safely(dispatcher, 1, False)
    assert result is (presence.PresenceResult.RETRY if retry else presence.PresenceResult.FAILED)


async def make_retry_due(manager, user_id):
    # Advance only the retry deadline, not asyncio's clock or send deadlines.
    # The real dispatcher must select and execute the retry itself.
    delay, _ = manager.retry_presence[user_id]
    manager.retry_presence[user_id] = (delay, 0)
    manager.schedule_presence(999)  # Wake a worker already waiting on its timer.
    await settle(manager)


async def test_persistent_transient_failure_backs_off_and_retains_offline_until_recovery(
    dispatcher, friendships, monkeypatch,
):
    manager = dispatcher
    observer, subject = Socket(), Socket()
    friendships[1] = [2]
    await ready(manager, observer, 2)
    await ready(manager, subject, 1)
    observer.send_json.reset_mock()
    attempts, failing = 0, True

    def lookup(user_id):
        nonlocal attempts
        if user_id == 1:
            attempts += 1
            if failing:
                raise OSError("persistent outage")
        return friendships.get(user_id, [])

    monkeypatch.setattr(presence, "find_presence_recipients", lookup)
    manager.disconnect(subject, 1)
    await settle(manager)
    assert manager.retry_presence[1][0] == 1
    for expected_delay in (2, 4, 8, 16, 30, 30):
        await make_retry_due(manager, 1)
        assert manager.retry_presence[1][0] == expected_delay
        assert manager.retry_presence[1][1] > asyncio.get_running_loop().time()
        assert 1 not in manager.active_connections
        assert observer.events == []
    assert attempts == 7
    # New work does not bypass the backed-off deadline or trigger a busy loop.
    for _ in range(20):
        manager.schedule_presence(999)
        await settle(manager)
    assert attempts == 7
    failing = False
    await make_retry_due(manager, 1)
    assert attempts == 8
    assert manager.retry_presence == {}
    assert observer.events == [{"type": "presence", "data": {"user_id": 1, "online": False}}]


async def test_programming_error_is_reported_once_without_automatic_retry(
    dispatcher, monkeypatch, caplog,
):
    manager = dispatcher
    attempts = 0

    def lookup(user_id):
        nonlocal attempts
        if user_id == 1:
            attempts += 1
            raise RuntimeError("broken query implementation")
        return []

    monkeypatch.setattr(presence, "find_presence_recipients", lookup)
    manager.schedule_presence(1)  # A required offline update.
    await settle(manager)
    for _ in range(20):
        manager.schedule_presence(2)
        await settle(manager)
    assert attempts == 1
    assert manager.retry_presence == {}
    assert "online=False) was not delivered: non-transient failure" in caplog.text
    assert "reconnect clients to resync" in caplog.text
    assert not manager.presence_worker.done()


async def test_due_retries_do_not_overtake_fresh_initialization(dispatcher, monkeypatch):
    manager = dispatcher
    manager.FRESH_JOBS_PER_RETRY = 1  # Exercise the most aggressive scheduling.
    attempts = {}
    retry_started, release = asyncio.Event(), asyncio.Event()

    async def lookup(function, user_id):
        if user_id in (1, 2, 3):
            attempts[user_id] = attempts.get(user_id, 0) + 1
            if user_id == 1 and attempts[user_id] == 2:
                retry_started.set()
                await release.wait()
            raise OSError("still unavailable")
        return []

    monkeypatch.setattr(presence, "run_in_threadpool", lookup)
    for user_id in (1, 2, 3):
        manager.schedule_presence(user_id)
    await settle(manager)
    for user_id in (1, 2, 3):
        manager.retry_presence[user_id] = (1, 0)
    manager.schedule_presence(999)
    await asyncio.wait_for(retry_started.wait(), 1)
    socket = Socket()
    initialized, queued = asyncio.Event(), asyncio.Event()

    async def transport(event):
        assert attempts[2] == attempts[3] == 1
        initialized.set()

    socket.send_json.side_effect = transport
    await manager.connect(socket, 4)

    async def initialize():
        queued.set()
        return await manager.initialize(socket, 4)

    initialization = asyncio.create_task(initialize())
    try:
        await asyncio.wait_for(queued.wait(), 1)
    finally:
        release.set()
    assert await asyncio.wait_for(initialization, 1)
    assert initialized.is_set()
    await settle(manager)
    assert attempts == {1: 2, 2: 2, 3: 2}  # Retried users also make progress.


@pytest.mark.parametrize("during_lookup", [False, True])
async def test_shutdown_cancels_retry_wait_or_active_retry(dispatcher, monkeypatch, during_lookup):
    manager = dispatcher
    attempts = 0
    started, cancelled, blocked = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def lookup(function, user_id):
        nonlocal attempts
        if user_id != 1:
            return []
        attempts += 1
        if attempts == 1:
            raise OSError("temporary outage")
        started.set()
        try:
            await blocked.wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(presence, "run_in_threadpool", lookup)
    manager.schedule_presence(1)
    await settle(manager)
    if during_lookup:
        manager.retry_presence[1] = (1, 0)
        manager.schedule_presence(999)
        await asyncio.wait_for(started.wait(), 1)
    worker = manager.presence_worker
    await asyncio.wait_for(manager.stop(), 1)
    assert worker.cancelled()
    assert cancelled.is_set() is during_lookup
    assert manager.retry_presence == {}
    assert manager.pending_presence == set()
    assert manager.presence_queue.empty()
    assert attempts == (2 if during_lookup else 1)


@pytest.mark.parametrize("limit", ["global", "per_user"])
async def test_initialization_admission_limits_preserve_healthy_tabs_and_recover(dispatcher, limit):
    manager = dispatcher
    healthy = Socket()
    await ready(manager, healthy, 1)
    manager.MAX_INITIALIZATIONS = 2
    manager.MAX_INITIALIZATIONS_PER_USER = 2
    first, second, excess = Socket(), Socket(), Socket()
    await manager.connect(first, 1)
    await manager.connect(second, 1)
    rejected_user = 2 if limit == "global" else 1
    if limit == "per_user":
        manager.MAX_INITIALIZATIONS = 3
    with pytest.raises(WebSocketDisconnect) as rejected:
        await manager.connect(excess, rejected_user)
    assert rejected.value.code == 1013
    excess.accept.assert_not_awaited()
    excess.close.assert_awaited_once_with(code=1013)
    assert len(manager.initialization_admissions) == 2
    assert manager.active_connections == {1: {healthy, first, second}}
    await manager.broadcast("ready tab survives")
    assert healthy.events[-1]["data"]["text"] == "ready tab survives"
    assert await manager.initialize(first, 1)
    assert await manager.initialize(second, 1)
    assert manager.initialization_admissions == {}
    replacement = Socket()
    await ready(manager, replacement, rejected_user)
    assert manager.initialization_admissions == {}
    healthy.close.assert_not_awaited()


@pytest.mark.parametrize("failure", ["cancel", "timeout", "transport"])
async def test_inflight_accept_reserves_and_releases_admission(dispatcher, failure):
    manager = dispatcher
    manager.MAX_INITIALIZATIONS = 1
    socket, excess = Socket(), Socket()
    started, release = asyncio.Event(), asyncio.Event()

    async def accept():
        started.set()
        await release.wait()
        raise OSError("accept failed")

    socket.accept.side_effect = accept
    if failure == "timeout":
        manager.SEND_TIMEOUT = 0.05
    connecting = asyncio.create_task(manager.connect(socket, 1))
    await asyncio.wait_for(started.wait(), 1)
    with pytest.raises(WebSocketDisconnect):
        await manager.connect(excess, 2)
    if failure == "cancel":
        connecting.cancel()
        expected = asyncio.CancelledError
    elif failure == "timeout":
        expected = TimeoutError
    else:
        release.set()
        expected = OSError
    with pytest.raises(expected):
        await asyncio.wait_for(connecting, 1)
    assert manager.initialization_admissions == {}
    assert manager.active_connections == {}
    await ready(manager, Socket(), 2)


@pytest.mark.parametrize("failure", ["cancel", "timeout"])
async def test_initialization_churn_removes_queued_jobs_and_releases_capacity(
    dispatcher, monkeypatch, failure,
):
    manager = dispatcher
    manager.MAX_INITIALIZATIONS = 1
    manager.INITIALIZE_TIMEOUT = 0.01 if failure == "timeout" else 20
    started, release = asyncio.Event(), asyncio.Event()
    original = main.notify_presence_safely

    async def notify(manager, user_id, online):
        if user_id == 99:
            started.set()
            await release.wait()
        return await original(manager, user_id, online)

    monkeypatch.setattr(main, "notify_presence_safely", notify)
    manager.schedule_presence(99)
    await asyncio.wait_for(started.wait(), 1)
    try:
        for _ in range(12):
            socket = Socket()
            queued = asyncio.Event()
            await manager.connect(socket, 1)

            async def initialize():
                queued.set()
                return await manager.initialize(socket, 1)

            initialization = asyncio.create_task(initialize())
            await asyncio.wait_for(queued.wait(), 1)
            assert manager.presence_queue.qsize() == 2  # State + snapshot.
            if failure == "cancel":
                initialization.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await initialization
            else:
                assert not await asyncio.wait_for(initialization, 1)
            assert manager.initialization_admissions == {}
            assert manager.active_connections == {}
            assert manager.presence_queue.qsize() == 1  # Only coalesced state remains.
            socket.send_json.assert_not_awaited()
            socket.close.assert_awaited_once_with(code=1011)
    finally:
        release.set()
    await settle(manager)  # Pruning preserves join accounting.
    await ready(manager, Socket(), 1)
    assert manager.initialization_admissions == {}


async def test_messages_before_snapshot_lookup_finishes_are_not_buffered(dispatcher, monkeypatch):
    manager = dispatcher
    socket = Socket()
    await manager.connect(socket, 1)
    await settle(manager)
    started, release = asyncio.Event(), asyncio.Event()

    async def lookup(function, user_id):
        started.set()
        await release.wait()
        return []

    monkeypatch.setattr(presence, "run_in_threadpool", lookup)
    initialization = asyncio.create_task(manager.initialize(socket, 1))
    try:
        await asyncio.wait_for(started.wait(), 1)
        await manager.broadcast("too early")
        socket.send_json.assert_not_awaited()
    finally:
        release.set()
    assert await asyncio.wait_for(initialization, 1)
    await manager.broadcast("ready")
    assert socket.events == [
        {"type": "presence_snapshot", "data": {"online_user_ids": []}},
        {"type": "message", "data": {"text": "ready"}},
    ]


@pytest.mark.parametrize("failure_at", ["lookup", "send"])
async def test_snapshot_failure_releases_last_admission_slot(dispatcher, monkeypatch, failure_at):
    manager = dispatcher
    manager.MAX_INITIALIZATIONS = 1
    socket = Socket()
    await manager.connect(socket, 1)
    await settle(manager)
    original = presence.find_presence_recipients
    if failure_at == "lookup":
        monkeypatch.setattr(presence, "find_presence_recipients", Mock(side_effect=RuntimeError("bad query")))
    else:
        socket.send_json.side_effect = RuntimeError("closed socket")
    assert not await manager.initialize(socket, 1)
    assert manager.initialization_admissions == {}
    assert manager.active_connections == {}
    socket.close.assert_awaited_once_with(code=1011)
    monkeypatch.setattr(presence, "find_presence_recipients", original)
    await ready(manager, Socket(), 2)


async def test_cancelling_queued_snapshot_preserves_other_jobs_and_fifo(dispatcher, monkeypatch):
    manager = dispatcher
    started, release = asyncio.Event(), asyncio.Event()
    original = main.notify_presence_safely

    async def notify(manager, user_id, online):
        if user_id == 99:
            started.set()
            await release.wait()
        return await original(manager, user_id, online)

    monkeypatch.setattr(main, "notify_presence_safely", notify)
    manager.schedule_presence(99)
    await asyncio.wait_for(started.wait(), 1)
    sockets = [Socket() for _ in range(3)]
    initializations = []
    delivered = []

    async def initialize(socket, user_id, queued):
        queued.set()
        return await manager.initialize(socket, user_id)

    try:
        for user_id, socket in enumerate(sockets):
            async def send(event, user_id=user_id):
                delivered.append(user_id)
            socket.send_json.side_effect = send
            await manager.connect(socket, user_id)
            queued = asyncio.Event()
            task = asyncio.create_task(initialize(socket, user_id, queued))
            initializations.append(task)
            await asyncio.wait_for(queued.wait(), 1)
        initializations[1].cancel()
        with pytest.raises(asyncio.CancelledError):
            await initializations[1]
        assert len(manager.initialization_admissions) == 2
    finally:
        release.set()
        results = await asyncio.gather(*initializations, return_exceptions=True)
    assert results[0] is results[2] is True
    assert delivered == [0, 2]
    assert manager.initialization_admissions == {}
    assert manager.active_connections == {0: {sockets[0]}, 2: {sockets[2]}}
    await settle(manager)
