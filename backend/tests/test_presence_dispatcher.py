"""Deterministic interleavings through the real dispatcher and send path.

Database visibility/query integration is covered separately. Here only the
friend lookup and transports are replaced; no scheduler or cleanup is mocked.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocketDisconnect

import app.main as main
import app.realtime.presence as presence
from app.main import ConnectionManager

pytestmark = pytest.mark.anyio


class Socket:
    def __init__(self):
        self.accept = AsyncMock()
        self.close = AsyncMock()
        self.send_json = AsyncMock()

    @property
    def events(self):
        return [call.args[0] for call in self.send_json.await_args_list]


async def settle(manager):
    await asyncio.wait_for(manager.presence_queue.join(), timeout=1)


async def ready(manager, socket, user_id):
    await manager.connect(socket, user_id)
    assert await manager.initialize(socket, user_id)
    await settle(manager)


@pytest.fixture
def friendships(monkeypatch):
    graph = {}
    monkeypatch.setattr(presence, "find_presence_recipients", lambda user_id: graph.get(user_id, []))

    async def lookup(function, user_id):
        return function(user_id)

    monkeypatch.setattr(presence, "run_in_threadpool", lookup)
    return graph


@pytest.fixture
async def dispatcher(friendships):
    manager = ConnectionManager()
    manager.start()
    try:
        yield manager
    finally:
        await manager.stop()
    assert manager.active_connections == {}
    assert manager.initializing == set()
    assert manager.send_locks == {}
    assert manager.presence_worker is None
    assert manager.presence_queue.empty()


async def test_reconnect_cannot_overtake_offline_already_being_sent(dispatcher, friendships):
    manager = dispatcher
    friendships.update({1: [2], 2: [1]})
    observer, old, replacement = Socket(), Socket(), Socket()
    await ready(manager, observer, 2)
    await ready(manager, old, 1)
    observer.send_json.reset_mock()
    started, release = asyncio.Event(), asyncio.Event()
    delivered = []

    async def send(event):
        if not event["data"]["online"]:
            started.set()
            await release.wait()
        delivered.append(event["data"]["online"])

    observer.send_json.side_effect = send
    assert manager.disconnect(old, 1)
    await asyncio.wait_for(started.wait(), 1)
    try:
        await manager.connect(replacement, 1)
        assert delivered == []
    finally:
        release.set()
    assert await manager.initialize(replacement, 1)
    await settle(manager)
    assert delivered == [False, True]
    assert manager.active_connections[1] == {replacement}


async def test_rapid_reconnect_before_dispatch_coalesces_to_current_state(dispatcher, friendships):
    manager = dispatcher
    friendships[1] = [2]
    observer, old, replacement = Socket(), Socket(), Socket()
    await ready(manager, observer, 2)
    await ready(manager, old, 1)
    observer.send_json.reset_mock()
    manager.disconnect(old, 1)
    await manager.connect(replacement, 1)  # Mock accept does not yield.
    await settle(manager)
    assert observer.events == [{"type": "presence", "data": {"user_id": 1, "online": True}}]
    assert manager.presence_queue.empty()


@pytest.mark.parametrize("failure", [None, OSError, RuntimeError, WebSocketDisconnect])
async def test_concurrent_tabs_record_online_even_when_first_snapshot_fails(
    dispatcher, friendships, failure,
):
    manager = dispatcher
    friendships.update({1: [2], 2: [1]})
    observer, first, second = Socket(), Socket(), Socket()
    await ready(manager, observer, 2)
    observer.send_json.reset_mock()
    transitions = await asyncio.gather(manager.connect(first, 1), manager.connect(second, 1))
    assert sorted(transitions) == [False, True]
    if failure:
        first.send_json.side_effect = failure()
    results = await asyncio.gather(manager.initialize(first, 1), manager.initialize(second, 1))
    await settle(manager)
    assert results == [failure is None, True]
    assert observer.events == [{"type": "presence", "data": {"user_id": 1, "online": True}}]
    assert second.events == [{"type": "presence_snapshot", "data": {"online_user_ids": [2]}}]
    if failure:
        first.close.assert_awaited_once_with(code=1011)
        assert manager.active_connections[1] == {second}
    else:
        manager.disconnect(first, 1)
        await settle(manager)
        assert len(observer.events) == 1
    manager.disconnect(second, 1)
    await settle(manager)
    assert observer.events[-1] == {"type": "presence", "data": {"user_id": 1, "online": False}}
    assert len(observer.events) == 2


@pytest.mark.parametrize("initially_online", [False, True])
async def test_state_change_during_snapshot_send_arrives_after_snapshot(
    dispatcher, friendships, initially_online,
):
    manager = dispatcher
    friendships.update({1: [2], 2: [1]})
    newcomer, friend = Socket(), Socket()
    if initially_online:
        await ready(manager, friend, 2)
    started, release = asyncio.Event(), asyncio.Event()
    delivered = []

    async def send(event):
        if event["type"] == "presence_snapshot":
            started.set()
            await release.wait()
        delivered.append(event)

    newcomer.send_json.side_effect = send
    await manager.connect(newcomer, 1)
    initialization = asyncio.create_task(manager.initialize(newcomer, 1))
    try:
        await asyncio.wait_for(started.wait(), 1)
        assert newcomer in manager.initializing
        if initially_online:
            manager.disconnect(friend, 2)
        else:
            await manager.connect(friend, 2)
        # An independent sender uses the same lock as the snapshot writer.
        independent_started = asyncio.Event()

        async def independent_sender():
            independent_started.set()
            await manager.send_to_user(
                1, {"type": "message", "data": {"text": "during snapshot"}},
            )

        independent = asyncio.create_task(independent_sender())
        await asyncio.wait_for(independent_started.wait(), 1)
        assert not independent.done()
        release.set()
        assert await asyncio.wait_for(initialization, 1)
        await asyncio.wait_for(independent, 1)
        await settle(manager)
    finally:
        release.set()
        if not initialization.done():
            initialization.cancel()
        await asyncio.gather(initialization, return_exceptions=True)
    assert delivered[0] == {
        "type": "presence_snapshot", "data": {"online_user_ids": [2] if initially_online else []},
    }
    assert [event for event in delivered if event["type"] == "presence"] == [
        {"type": "presence", "data": {"user_id": 2, "online": not initially_online}},
    ]
    assert {event["type"] for event in delivered} == {"presence_snapshot", "presence", "message"}


async def test_snapshot_uses_state_after_database_lookup_not_before(dispatcher, friendships, monkeypatch):
    manager = dispatcher
    friendships.update({1: [2], 2: [1]})
    friend, newcomer = Socket(), Socket()
    await ready(manager, friend, 2)
    started, release = asyncio.Event(), asyncio.Event()
    original = presence.find_presence_recipients
    calls = 0

    async def lookup(function, user_id):
        nonlocal calls
        if user_id == 1:
            calls += 1
            if calls == 2:  # Initial online update, then snapshot lookup.
                started.set()
                await release.wait()
        return original(user_id)

    monkeypatch.setattr(presence, "run_in_threadpool", lookup)
    await manager.connect(newcomer, 1)
    initialization = asyncio.create_task(manager.initialize(newcomer, 1))
    try:
        await asyncio.wait_for(started.wait(), 1)
        manager.disconnect(friend, 2)
    finally:
        release.set()
    assert await asyncio.wait_for(initialization, 1)
    await settle(manager)
    assert newcomer.events[0] == {"type": "presence_snapshot", "data": {"online_user_ids": []}}
    assert newcomer.events[-1] == {"type": "presence", "data": {"user_id": 2, "online": False}}


async def test_failed_recipient_queues_offline_without_recursive_delivery(dispatcher, friendships, monkeypatch):
    manager = dispatcher
    a, b, observer = Socket(), Socket(), Socket()
    for user_id, socket in ((1, a), (2, b), (3, observer)):
        await ready(manager, socket, user_id)
    friendships.update({1: [2, 3], 2: [3]})
    b.send_json.side_effect = OSError("lost transport")
    observer.send_json.reset_mock()
    depth = 0
    original = main.notify_presence_safely

    async def notify(*args):
        nonlocal depth
        depth += 1
        assert depth == 1
        try:
            return await original(*args)
        finally:
            depth -= 1

    monkeypatch.setattr(main, "notify_presence_safely", notify)
    manager.schedule_presence(1)
    await settle(manager)
    assert observer.events == [
        {"type": "presence", "data": {"user_id": 1, "online": True}},
        {"type": "presence", "data": {"user_id": 2, "online": False}},
    ]
    assert 2 not in manager.active_connections
    assert manager.presence_worker is not None and not manager.presence_worker.done()


async def test_failed_lookup_is_retried_without_new_transition(dispatcher, friendships, monkeypatch):
    manager = dispatcher
    observer, subject = Socket(), Socket()
    await ready(manager, observer, 2)
    await ready(manager, subject, 1)
    observer.send_json.reset_mock()
    friendships[1] = [2]
    unavailable, recovered = asyncio.Event(), asyncio.Event()
    attempts = 0

    def lookup(user_id):
        nonlocal attempts
        if user_id == 1:
            attempts += 1
            if attempts == 1:
                unavailable.set()
                raise OSError("database temporarily unavailable")
            recovered.set()
        return friendships.get(user_id, [])

    monkeypatch.setattr(presence, "find_presence_recipients", lookup)
    # A small retry interval only accelerates a timer; events control assertions.
    manager.RETRY_INTERVAL = 0.01
    manager.schedule_presence(1)
    await asyncio.wait_for(unavailable.wait(), 1)
    await settle(manager)
    assert 1 in manager.retry_presence
    await asyncio.wait_for(recovered.wait(), 2)
    await settle(manager)
    assert attempts == 2
    assert manager.retry_presence == {}
    assert observer.events == [{"type": "presence", "data": {"user_id": 1, "online": True}}]


async def test_new_transition_supersedes_failed_update(dispatcher, friendships, monkeypatch):
    manager = dispatcher
    observer, subject = Socket(), Socket()
    await ready(manager, observer, 2)
    await ready(manager, subject, 1)
    observer.send_json.reset_mock()
    friendships[1] = [2]
    fail = True

    def lookup(user_id):
        if fail:
            raise OSError("database temporarily unavailable")
        return friendships.get(user_id, [])

    monkeypatch.setattr(presence, "find_presence_recipients", lookup)
    manager.schedule_presence(1)
    await settle(manager)
    assert set(manager.retry_presence) == {1}
    fail = False
    manager.disconnect(subject, 1)
    await settle(manager)
    assert manager.retry_presence == {}
    assert observer.events == [{"type": "presence", "data": {"user_id": 1, "online": False}}]


@pytest.mark.parametrize("operation", ["snapshot_lookup", "snapshot_send", "live_send"])
async def test_stalled_operation_is_bounded_and_healthy_socket_survives(
    dispatcher, friendships, monkeypatch, operation,
):
    manager = dispatcher
    healthy, stalled = Socket(), Socket()
    await ready(manager, healthy, 2)
    blocked = asyncio.Event()
    manager.SEND_TIMEOUT = 0.01
    monkeypatch.setattr(presence, "DB_TIMEOUT", 0.01)
    await manager.connect(stalled, 1)
    if operation == "snapshot_lookup":
        async def lookup(function, user_id):
            if user_id == 1:
                await blocked.wait()
            return []
        monkeypatch.setattr(presence, "run_in_threadpool", lookup)
    elif operation == "snapshot_send":
        stalled.send_json.side_effect = lambda event: None
        async def send(event):
            await blocked.wait()
        stalled.send_json.side_effect = send
    else:
        assert await manager.initialize(stalled, 1)
        async def send(event):
            await blocked.wait()
        stalled.send_json.side_effect = send
    if operation.startswith("snapshot"):
        assert not await asyncio.wait_for(manager.initialize(stalled, 1), 1)
    else:
        await asyncio.wait_for(manager.broadcast("survives"), 1)
    assert manager.active_connections == {2: {healthy}}
    stalled.close.assert_awaited_once_with(code=1011)
    await manager.send_to_user(2, {"type": "message", "data": {"text": "healthy"}})
    assert healthy.events[-1]["data"]["text"] == "healthy"


async def test_initialization_queue_wait_has_deadline(dispatcher, monkeypatch):
    manager = dispatcher
    manager.INITIALIZE_TIMEOUT = 0.01
    started, release = asyncio.Event(), asyncio.Event()

    async def notify(*args):
        started.set()
        await release.wait()
        return True

    monkeypatch.setattr(main, "notify_presence_safely", notify)
    socket = Socket()
    await manager.connect(socket, 1)
    await asyncio.wait_for(started.wait(), 1)
    try:
        assert not await asyncio.wait_for(manager.initialize(socket, 1), 1)
        assert manager.active_connections == {}
    finally:
        release.set()
    await settle(manager)
    socket.send_json.assert_not_awaited()
    socket.close.assert_awaited_once_with(code=1011)


async def test_lifespan_owns_single_worker_and_can_restart(friendships):
    manager = main.manager
    for _ in range(2):
        async with main.app.router.lifespan_context(main.app):
            worker = manager.presence_worker
            manager.start()
            assert manager.presence_worker is worker
            socket = Socket()
            await ready(manager, socket, 1)
        assert worker.cancelled()
        assert manager.presence_worker is None
        assert manager.active_connections == {}
        assert manager.pending_presence == set()
        socket.close.assert_awaited_once_with(code=1011)


async def test_shutdown_cancels_active_snapshot_and_resolves_queued_initializations(friendships):
    manager = ConnectionManager()
    manager.start()
    a, b = Socket(), Socket()
    started, blocked = asyncio.Event(), asyncio.Event()

    async def send(event):
        started.set()
        await blocked.wait()

    a.send_json.side_effect = send
    await manager.connect(a, 1)
    await manager.connect(b, 2)
    first = asyncio.create_task(manager.initialize(a, 1))
    second = asyncio.create_task(manager.initialize(b, 2))
    try:
        await asyncio.wait_for(started.wait(), 1)
        assert not first.done() and not second.done()
        await asyncio.wait_for(manager.stop(), 1)
        assert await first is False
        assert await second is False
    finally:
        await manager.stop()
        await asyncio.gather(first, second, return_exceptions=True)
    assert manager.active_connections == {}
    assert manager.send_locks == {}
    assert manager.presence_queue.empty()
    a.close.assert_awaited_once_with(code=1011)
    b.close.assert_awaited_once_with(code=1011)


async def test_cancelled_initialization_removes_socket_without_live_delivery(dispatcher):
    manager = dispatcher
    socket = Socket()
    started, release = asyncio.Event(), asyncio.Event()

    async def send(event):
        started.set()
        await release.wait()

    socket.send_json.side_effect = send
    await manager.connect(socket, 1)
    initialization = asyncio.create_task(manager.initialize(socket, 1))
    try:
        await asyncio.wait_for(started.wait(), 1)
        initialization.cancel()
        with pytest.raises(asyncio.CancelledError):
            await initialization
        assert manager.active_connections == {}
    finally:
        release.set()
    await settle(manager)
    assert manager.initializing == set()
    assert manager.send_locks == {}
    socket.close.assert_awaited_once_with(code=1011)


async def test_interrupted_update_is_retained_for_explicit_dispatcher_restart(
    dispatcher, friendships, monkeypatch,
):
    manager = dispatcher
    friendships[1] = [2]
    observer, subject = Socket(), Socket()
    await ready(manager, observer, 2)
    await ready(manager, subject, 1)
    observer.send_json.reset_mock()
    started, blocked = asyncio.Event(), asyncio.Event()
    original = presence.run_in_threadpool

    async def lookup(function, user_id):
        started.set()
        await blocked.wait()

    monkeypatch.setattr(presence, "run_in_threadpool", lookup)
    manager.schedule_presence(1)
    await asyncio.wait_for(started.wait(), 1)
    worker = manager.presence_worker
    worker.cancel()
    await asyncio.gather(worker, return_exceptions=True)
    assert 1 in manager.pending_presence
    assert manager.presence_queue.qsize() == 1
    monkeypatch.setattr(presence, "run_in_threadpool", original)
    manager.start()
    assert manager.presence_worker is not worker
    await settle(manager)
    assert observer.events == [{"type": "presence", "data": {"user_id": 1, "online": True}}]


async def test_accept_finishing_during_shutdown_cannot_register(dispatcher):
    manager = dispatcher
    socket = Socket()
    started, release = asyncio.Event(), asyncio.Event()

    async def accept():
        started.set()
        await release.wait()

    socket.accept.side_effect = accept
    connecting = asyncio.create_task(manager.connect(socket, 1))
    try:
        await asyncio.wait_for(started.wait(), 1)
        await manager.stop()
    finally:
        release.set()
    with pytest.raises(WebSocketDisconnect):
        await connecting
    assert manager.active_connections == {}
    assert manager.presence_queue.empty()
    socket.close.assert_awaited_once_with(code=1011)


async def test_stalled_close_does_not_block_healthy_recipient(dispatcher):
    manager = dispatcher
    failed, healthy = Socket(), Socket()
    await ready(manager, failed, 1)
    await ready(manager, healthy, 2)
    failed.send_json.side_effect = OSError("broken")
    blocked, cancelled = asyncio.Event(), asyncio.Event()

    async def close(**kwargs):
        try:
            await blocked.wait()
        finally:
            cancelled.set()

    failed.close.side_effect = close
    manager.CLOSE_TIMEOUT = 0.01
    await asyncio.wait_for(manager.broadcast("healthy"), 1)
    assert cancelled.is_set()
    assert manager.active_connections == {2: {healthy}}
    assert healthy.events[-1] == {"type": "message", "data": {"text": "healthy"}}
