"""User and tab bookkeeping, targeted delivery, and failed-send cleanup."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, call

import pytest
from fastapi import WebSocket, WebSocketDisconnect

from app.main import ConnectionManager
import app.main as main

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def presence_notification(monkeypatch):
    # Isolate bookkeeping/delivery from initialization and the dispatcher.
    # End-to-end snapshot gating is exercised in test_presence_dispatcher.py.
    connect = ConnectionManager.connect
    offline = Mock()

    async def ready_connect(manager, socket, user_id):
        result = await connect(manager, socket, user_id)
        manager.initializing.discard(socket)
        manager.initialization_admissions.pop(socket, None)
        return result

    def schedule(manager, user_id):
        if user_id not in manager.active_connections:
            offline(manager, user_id, False)

    monkeypatch.setattr(ConnectionManager, "connect", ready_connect)
    monkeypatch.setattr(ConnectionManager, "schedule_presence", schedule)
    return offline


async def test_first_connection_per_user_goes_online_and_extra_tabs_do_not():
    manager = ConnectionManager()
    alice, alice_tab, bob, bob_tab = [MagicMock(spec=WebSocket) for _ in range(4)]

    assert await manager.connect(alice, 1) is True
    assert await manager.connect(alice_tab, 1) is False
    assert await manager.connect(bob, 2) is True
    assert await manager.connect(bob_tab, 2) is False

    assert manager.active_connections == {1: {alice, alice_tab}, 2: {bob, bob_tab}}
    for socket in (alice, alice_tab, bob, bob_tab):
        socket.accept.assert_awaited_once_with()


async def test_only_final_tab_disconnect_goes_offline_and_duplicates_are_harmless():
    manager = ConnectionManager()
    alice, alice_tab, bob = [MagicMock(spec=WebSocket) for _ in range(3)]
    await manager.connect(alice, 1)
    await manager.connect(alice_tab, 1)
    await manager.connect(bob, 2)

    assert manager.disconnect(alice, 2) is False  # Wrong user must not remove Bob.
    assert manager.disconnect(alice, 999) is False
    assert manager.active_connections == {1: {alice, alice_tab}, 2: {bob}}
    assert manager.disconnect(alice, 1) is False
    assert manager.disconnect(alice, 1) is False
    assert manager.active_connections == {1: {alice_tab}, 2: {bob}}
    assert manager.disconnect(alice_tab, 1) is True
    assert manager.disconnect(alice_tab, 1) is False
    assert manager.active_connections == {2: {bob}}
    assert manager.disconnect(bob, 2) is True
    assert manager.active_connections == {}
    assert await manager.connect(alice, 1) is True


async def test_failed_accept_does_not_register_a_connection():
    manager = ConnectionManager()
    socket = MagicMock(spec=WebSocket)
    socket.accept.side_effect = OSError("handshake failed")

    with pytest.raises(OSError, match="handshake failed"):
        await manager.connect(socket, 1)

    assert manager.active_connections == {}


async def test_broadcast_reaches_multiple_users_and_every_tab():
    manager = ConnectionManager()
    sockets = [MagicMock(spec=WebSocket) for _ in range(4)]
    for user_id, socket in zip((1, 1, 2, 2), sockets):
        await manager.connect(socket, user_id)

    await manager.broadcast("hello 🎵")

    for socket in sockets:
        socket.send_json.assert_awaited_once_with(
            {"type": "message", "data": {"text": "hello 🎵"}}
        )


async def test_send_to_user_reaches_every_target_tab_and_no_other_user():
    manager = ConnectionManager()
    alice, alice_tab, bob, bob_tab = [MagicMock(spec=WebSocket) for _ in range(4)]
    for user_id, socket in ((1, alice), (1, alice_tab), (2, bob), (2, bob_tab)):
        await manager.connect(socket, user_id)
    event = {"type": "presence", "data": {"user_id": 3, "online": True}}

    await manager.send_to_user(1, event)

    alice.send_json.assert_awaited_once_with(event)
    alice_tab.send_json.assert_awaited_once_with(event)
    bob.send_json.assert_not_awaited()
    bob_tab.send_json.assert_not_awaited()
    assert manager.active_connections == {1: {alice, alice_tab}, 2: {bob, bob_tab}}


async def test_sending_to_offline_users_and_broadcasting_without_connections_are_harmless():
    manager = ConnectionManager()
    await manager.broadcast("nobody here")
    await manager.send_to_user(999, {"type": "presence"})
    assert manager.active_connections == {}

    socket = MagicMock(spec=WebSocket)
    await manager.connect(socket, 1)
    await manager.send_to_user(999, {"type": "presence"})
    socket.send_json.assert_not_awaited()
    assert manager.active_connections == {1: {socket}}


@pytest.mark.parametrize("delivery", ["broadcast", "send_to_user"])
@pytest.mark.parametrize("failure", [WebSocketDisconnect, OSError, RuntimeError])
@pytest.mark.parametrize("healthy_tab", [False, True], ids=["last-tab", "healthy-sibling"])
async def test_failed_send_removes_only_broken_sockets_and_delivery_continues(
    delivery, failure, healthy_tab, presence_notification,
):
    manager = ConnectionManager()
    broken, sibling, other = [MagicMock(spec=WebSocket) for _ in range(3)]
    broken.send_json.side_effect = failure()
    await manager.connect(broken, 1)
    if healthy_tab:
        await manager.connect(sibling, 1)
    await manager.connect(other, 2)
    event = {"type": "message", "data": {"text": "delivered"}}

    if delivery == "broadcast":
        await manager.broadcast("delivered")
        other.send_json.assert_awaited_once_with(event)
    else:
        await manager.send_to_user(1, event)
        other.send_json.assert_not_awaited()

    broken.send_json.assert_awaited_once_with(event)
    assert manager.disconnect(broken, 1) is False
    if healthy_tab:
        sibling.send_json.assert_awaited_once_with(event)
        assert manager.active_connections == {1: {sibling}, 2: {other}}
    else:
        assert manager.active_connections == {2: {other}}

    # Subsequent delivery must not retry a socket that was already removed.
    if delivery == "broadcast":
        await manager.broadcast("delivered")
        assert other.send_json.await_count == 2
    else:
        await manager.send_to_user(1, event)
    assert broken.send_json.await_count == 1
    if healthy_tab:
        assert sibling.send_json.await_count == 2
        presence_notification.assert_not_called()
    else:
        presence_notification.assert_called_once_with(manager, 1, False)


@pytest.mark.parametrize("delivery", ["broadcast", "send_to_user"])
@pytest.mark.parametrize("cleanup_delivery", ["broadcast", "send_to_user"])
@pytest.mark.parametrize("healthy_tab", [False, True], ids=["last-tab", "healthy-sibling"])
async def test_copied_socket_is_skipped_after_concurrent_failed_send_removes_it(
    monkeypatch, delivery, cleanup_delivery, healthy_tab, presence_notification,
):
    manager = ConnectionManager()
    broken, sibling, other = [MagicMock(spec=WebSocket) for _ in range(3)]
    broken.send_json.side_effect = OSError("transport lost")
    await manager.connect(broken, 1)
    if healthy_tab:
        await manager.connect(sibling, 1)
    await manager.connect(other, 2)

    copied_socket_reached, resume_delivery = asyncio.Event(), asyncio.Event()
    send_event = manager.send_event

    async def pause_before_membership_check(socket, user_id, event):
        if socket is broken and event["data"]["text"] == "older":
            # The delivery loop has copied its set and selected this socket.
            # Pause before send_event can check whether it is still registered.
            copied_socket_reached.set()
            await resume_delivery.wait()
        await send_event(socket, user_id, event)

    monkeypatch.setattr(manager, "send_event", pause_before_membership_check)

    async def deliver(method, text):
        if method == "broadcast":
            await manager.broadcast(text)
        else:
            await manager.send_to_user(1, {"type": "message", "data": {"text": text}})

    older_delivery = asyncio.create_task(deliver(delivery, "older"))
    try:
        await asyncio.wait_for(copied_socket_reached.wait(), timeout=1)
        broken.send_json.assert_not_awaited()

        await asyncio.wait_for(deliver(cleanup_delivery, "cleanup"), timeout=1)
        assert broken not in manager.active_connections.get(1, set())
        resume_delivery.set()
        await asyncio.wait_for(older_delivery, timeout=1)
    finally:
        resume_delivery.set()
        if not older_delivery.done():
            older_delivery.cancel()
        await asyncio.gather(older_delivery, return_exceptions=True)

    # The stale copy must not attempt a second transport send, even though
    # catching that second exception could otherwise hide the regression.
    broken.send_json.assert_awaited_once_with(
        {"type": "message", "data": {"text": "cleanup"}},
    )
    assert manager.disconnect(broken, 1) is False
    assert manager.active_connections == (
        {1: {sibling}, 2: {other}} if healthy_tab else {2: {other}}
    )
    if healthy_tab:
        sibling.send_json.assert_has_awaits([
            call({"type": "message", "data": {"text": text}})
            for text in ("older", "cleanup")
        ], any_order=True)
        assert sibling.send_json.await_count == 2
        presence_notification.assert_not_called()
    else:
        presence_notification.assert_called_once_with(manager, 1, False)

    expected_other = [
        call({"type": "message", "data": {"text": text}})
        for method, text in ((delivery, "older"), (cleanup_delivery, "cleanup"))
        if method == "broadcast"
    ]
    other.send_json.assert_has_awaits(expected_other, any_order=True)
    assert other.send_json.await_count == len(expected_other)
