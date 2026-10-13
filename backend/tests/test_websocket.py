"""Tests for the authenticated in-memory WebSocket transport.

The ASGI harness keeps every client on one event loop, making assertions about
the process-wide connection manager deterministic.
"""

import asyncio
import json
import logging
import threading
from contextlib import AsyncExitStack, asynccontextmanager
from http.cookies import SimpleCookie
from unittest.mock import AsyncMock, Mock, call

import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError

import app.main as main
import app.auth.websocket as websocket_auth
import app.realtime.presence as presence
from app.auth.constants import SESSION_COOKIE_NAME
from app.main import app, manager

ALLOWED_ORIGIN = "http://localhost:5173"
SESSION_TOKEN = "test-session-token"


class ASGIWebSocketSession:
    """Drive one WebSocket connection through the FastAPI ASGI application."""

    def __init__(self, path="/ws", *, headers=None, cookies=None):
        self._incoming = asyncio.Queue()
        self._outgoing = asyncio.Queue()
        self._task = None
        handshake_headers = [
            (name.lower().encode("latin-1"), value.encode("latin-1"))
            for name, value in (headers or {}).items()
        ]
        if cookies:
            cookie = SimpleCookie()
            for name, value in cookies.items():
                cookie[name] = value
            handshake_headers.append(
                (b"cookie", cookie.output(header="", sep=";").strip().encode("latin-1"))
            )
        self._scope = {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "scheme": "ws",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "root_path": "",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": handshake_headers,
            "subprotocols": [],
            "state": {},
            "extensions": {},
        }

    async def handshake(self):
        self._task = asyncio.create_task(
            app(self._scope, self._incoming.get, self._outgoing.put)
        )
        await self._incoming.put({"type": "websocket.connect"})
        return await self._receive()

    async def connect(self):
        assert await self.handshake() == {
            "type": "websocket.accept",
            "subprotocol": None,
            "headers": [],
        }

    async def assert_rejected(self):
        assert await self.handshake() == {
            "type": "websocket.close", "code": 1008, "reason": ""
        }
        await self.wait_until_closed()
        assert self._outgoing.empty()

    async def send_text(self, text):
        await self._incoming.put({"type": "websocket.receive", "text": text})

    async def receive_json(self):
        message = await self._receive()
        assert message["type"] == "websocket.send"
        return json.loads(message["text"])

    async def disconnect(self):
        if self._task.done():
            await self._task
            return

        await self._incoming.put(
            {"type": "websocket.disconnect", "code": 1000, "reason": ""}
        )
        await asyncio.wait_for(self._task, timeout=1)

    async def wait_until_closed(self):
        await asyncio.wait_for(self._task, timeout=1)

    async def _receive(self):
        return await asyncio.wait_for(self._outgoing.get(), timeout=1)


@asynccontextmanager
async def connected_websocket(token=SESSION_TOKEN, *, online_user_ids=()):
    websocket = ASGIWebSocketSession(
        headers={"origin": ALLOWED_ORIGIN},
        cookies={SESSION_COOKIE_NAME: token},
    )
    await websocket.connect()
    try:
        # None is reserved for tests where snapshot creation intentionally fails.
        if online_user_ids is not None:
            assert await websocket.receive_json() == {
                "type": "presence_snapshot",
                "data": {"online_user_ids": list(online_user_ids)},
            }
        yield websocket
    finally:
        await websocket.disconnect()


@pytest.fixture(autouse=True)
def forbid_database_access(monkeypatch):
    """Endpoint tests must never reach the configured database."""
    factory = Mock(side_effect=AssertionError("unexpected database access"))
    monkeypatch.setattr(websocket_auth, "SessionLocal", factory)
    monkeypatch.setattr(presence, "SessionLocal", factory)
    yield factory
    factory.assert_not_called()


@pytest.fixture(autouse=True)
def friendship_lookup(monkeypatch):
    lookup = Mock(return_value=[])
    monkeypatch.setattr(presence, "find_presence_recipients", lookup)
    return lookup


@pytest.fixture(autouse=True)
def presence_notification(monkeypatch):
    notify = AsyncMock()
    monkeypatch.setattr(main, "notify_presence_safely", notify)
    return notify


@pytest.fixture
def authenticated_user(monkeypatch):
    authenticate = Mock(return_value=42)
    monkeypatch.setattr(main, "authenticate_websocket", authenticate)
    return authenticate


@pytest.fixture
def manager_connect(monkeypatch):
    connect = AsyncMock(wraps=manager.connect)
    monkeypatch.setattr(manager, "connect", connect)
    return connect


@pytest.fixture(autouse=True)
def websocket_connection_state_does_not_leak_between_tests():
    """Every transport test must leave the process-wide manager empty."""
    assert manager.active_connections == {}
    yield
    assert manager.active_connections == {}


@pytest.mark.anyio
async def test_client_can_connect_and_is_removed_when_it_disconnects(authenticated_user):
    async with connected_websocket():
        assert len(manager.active_connections) == 1

    assert manager.active_connections == {}
    authenticated_user.assert_called_once_with(SESSION_TOKEN)


@pytest.mark.anyio
async def test_broadcast_reaches_all_clients_including_the_sender(authenticated_user):
    expected_event = {"type": "message", "data": {"text": "hello everyone"}}

    async with connected_websocket() as sender:
        async with connected_websocket() as recipient:
            assert len(manager.active_connections[42]) == 2

            await sender.send_text("hello everyone")

            assert await sender.receive_json() == expected_event
            assert await recipient.receive_json() == expected_event


@pytest.mark.anyio
async def test_remaining_client_keeps_receiving_after_another_disconnects(authenticated_user):
    expected_event = {"type": "message", "data": {"text": "still here"}}

    async with connected_websocket() as remaining_client:
        async with connected_websocket():
            assert len(manager.active_connections[42]) == 2

        assert len(manager.active_connections[42]) == 1
        await remaining_client.send_text("still here")
        assert await remaining_client.receive_json() == expected_event


@pytest.mark.anyio
async def test_unexpected_endpoint_error_still_removes_connection(
    monkeypatch, authenticated_user, presence_notification,
):
    async def fail_to_broadcast(_message):
        raise RuntimeError("unexpected broadcast failure")

    monkeypatch.setattr(manager, "broadcast", fail_to_broadcast)
    websocket = ASGIWebSocketSession(
        headers={"origin": ALLOWED_ORIGIN},
        cookies={SESSION_COOKIE_NAME: SESSION_TOKEN},
    )
    await websocket.connect()
    assert await websocket.receive_json() == {
        "type": "presence_snapshot", "data": {"online_user_ids": []},
    }
    await websocket.send_text("trigger failure")

    with pytest.raises(RuntimeError, match="unexpected broadcast failure"):
        await websocket.wait_until_closed()

    assert manager.active_connections == {}
    assert presence_notification.await_args_list == [
        call(manager, 42, True), call(manager, 42, False),
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("origin", [
    None, "null", "https://evil.example", "http://localhost:5173.evil.example",
    "http://localhost:5174", "https://localhost:5173",
])
async def test_unauthorized_origin_is_rejected_before_authentication(
    origin, authenticated_user, manager_connect, forbid_database_access,
    presence_notification, friendship_lookup,
):
    websocket = ASGIWebSocketSession(
        headers={} if origin is None else {"origin": origin},
        cookies={SESSION_COOKIE_NAME: SESSION_TOKEN},
    )

    await websocket.assert_rejected()

    authenticated_user.assert_not_called()
    forbid_database_access.assert_not_called()
    manager_connect.assert_not_called()
    presence_notification.assert_not_called()
    friendship_lookup.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("cookies", [
    {}, {SESSION_COOKIE_NAME: ""}, {"session": SESSION_TOKEN},
])
async def test_missing_cookie_is_rejected_before_authentication(
    cookies, authenticated_user, manager_connect, forbid_database_access,
    presence_notification, friendship_lookup,
):
    websocket = ASGIWebSocketSession(
        headers={"origin": ALLOWED_ORIGIN}, cookies=cookies,
    )

    await websocket.assert_rejected()

    authenticated_user.assert_not_called()
    forbid_database_access.assert_not_called()
    manager_connect.assert_not_called()
    presence_notification.assert_not_called()
    friendship_lookup.assert_not_called()


@pytest.mark.anyio
async def test_invalid_authentication_never_enters_connection_manager(
    authenticated_user, manager_connect, presence_notification, friendship_lookup,
):
    authenticated_user.return_value = None
    websocket = ASGIWebSocketSession(
        headers={"origin": ALLOWED_ORIGIN},
        cookies={SESSION_COOKIE_NAME: SESSION_TOKEN},
    )

    await websocket.assert_rejected()

    authenticated_user.assert_called_once_with(SESSION_TOKEN)
    manager_connect.assert_not_called()
    presence_notification.assert_not_called()
    friendship_lookup.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("origin", [ALLOWED_ORIGIN, "http://127.0.0.1:5173"])
async def test_authentication_runs_in_threadpool_before_accepting(
    monkeypatch, origin, manager_connect, friendship_lookup,
):
    event_loop_thread = threading.get_ident()

    def authenticate(token):
        assert token == SESSION_TOKEN
        assert threading.get_ident() != event_loop_thread
        assert manager.active_connections == {}
        manager_connect.assert_not_called()
        friendship_lookup.assert_not_called()
        assert websocket._outgoing.empty()
        return 42

    authentication = Mock(side_effect=authenticate)
    monkeypatch.setattr(main, "authenticate_websocket", authentication)
    threadpool = AsyncMock(wraps=main.run_in_threadpool)
    monkeypatch.setattr(main, "run_in_threadpool", threadpool)
    websocket = ASGIWebSocketSession(
        headers={"Origin": origin},
        cookies={"unrelated": "ignored", SESSION_COOKIE_NAME: SESSION_TOKEN},
    )

    await websocket.connect()
    try:
        threadpool.assert_awaited_once_with(authentication, SESSION_TOKEN)
        authentication.assert_called_once_with(SESSION_TOKEN)
        manager_connect.assert_awaited_once()
        assert len(manager.active_connections) == 1
        assert await websocket.receive_json() == {
            "type": "presence_snapshot", "data": {"online_user_ids": []},
        }
        friendship_lookup.assert_called_once_with(42)
        await websocket.send_text("authenticated 🎵")
        assert await websocket.receive_json() == {
            "type": "message", "data": {"text": "authenticated 🎵"}
        }
    finally:
        await websocket.disconnect()


@pytest.mark.anyio
async def test_presence_notifications_follow_first_and_last_tab_transitions(
    authenticated_user, presence_notification,
):
    async with connected_websocket() as first_tab:
        # A round trip ensures the endpoint has finished its online notification.
        await first_tab.send_text("first tab ready")
        await first_tab.receive_json()
        presence_notification.assert_awaited_once_with(manager, 42, True)

        async with connected_websocket() as second_tab:
            await second_tab.send_text("second tab ready")
            await first_tab.receive_json()
            await second_tab.receive_json()
            assert len(manager.active_connections[42]) == 2
            presence_notification.assert_awaited_once_with(manager, 42, True)

        assert len(manager.active_connections[42]) == 1
        presence_notification.assert_awaited_once_with(manager, 42, True)

    assert presence_notification.await_args_list == [
        call(manager, 42, True), call(manager, 42, False),
    ]
    assert manager.active_connections == {}

    # Reconnecting starts a new online/offline cycle.
    async with connected_websocket() as reconnected:
        await reconnected.send_text("back again")
        await reconnected.receive_json()
    assert presence_notification.await_args_list == [
        call(manager, 42, True), call(manager, 42, False),
        call(manager, 42, True), call(manager, 42, False),
    ]


@pytest.mark.anyio
async def test_endpoint_delivers_presence_through_real_safe_notifier(
    monkeypatch, authenticated_user,
):
    authenticated_user.side_effect = lambda token: 7 if token == "friend-token" else 42
    monkeypatch.setattr(main, "notify_presence_safely", presence.notify_presence_safely)
    lookup = Mock(side_effect=lambda user_id: [7] if user_id == 42 else [])
    monkeypatch.setattr(presence, "find_presence_recipients", lookup)

    async with connected_websocket("friend-token") as friend:
        async with connected_websocket("friend-token") as friend_tab:
            # Both recipient tabs are registered before the subject connects.
            await friend_tab.send_text("friends ready")
            await friend.receive_json()
            await friend_tab.receive_json()

            async with connected_websocket(online_user_ids=[7]):
                online = {"type": "presence", "data": {"user_id": 42, "online": True}}
                assert await friend.receive_json() == online
                assert await friend_tab.receive_json() == online

            offline = {"type": "presence", "data": {"user_id": 42, "online": False}}
            assert await friend.receive_json() == offline
            assert await friend_tab.receive_json() == offline


@pytest.mark.anyio
async def test_notification_failure_does_not_terminate_a_healthy_websocket(
    monkeypatch, authenticated_user, caplog,
):
    # Keep the actual safe wrapper: replacing it with a raising mock would test
    # behavior the wrapper explicitly prevents.
    safe_notify = AsyncMock(wraps=presence.notify_presence_safely)
    monkeypatch.setattr(main, "notify_presence_safely", safe_notify)
    error = RuntimeError("presence lookup unavailable")
    # Snapshot succeeds; online and offline notification lookups fail.
    lookup = Mock(side_effect=[[], error, error])
    monkeypatch.setattr(presence, "find_presence_recipients", lookup)

    with caplog.at_level(logging.ERROR, logger=presence.__name__):
        async with connected_websocket() as websocket:
            for message in ("still healthy", "still receiving"):
                await websocket.send_text(message)
                assert await websocket.receive_json() == {
                    "type": "message", "data": {"text": message},
                }
            assert len(manager.active_connections[42]) == 1
            assert not websocket._task.done()

    assert manager.active_connections == {}
    assert safe_notify.await_args_list == [call(manager, 42, True), call(manager, 42, False)]
    assert lookup.call_args_list == [call(42), call(42), call(42)]
    records = [record for record in caplog.records if record.name == presence.__name__]
    assert len(records) == 2
    assert all(isinstance(record.exc_info[1], RuntimeError) for record in records)


@pytest.mark.anyio
async def test_unexpected_authentication_error_never_registers_a_connection(
    authenticated_user, manager_connect, presence_notification, friendship_lookup,
):
    authenticated_user.side_effect = RuntimeError("authentication unavailable")
    websocket = ASGIWebSocketSession(
        headers={"origin": ALLOWED_ORIGIN},
        cookies={SESSION_COOKIE_NAME: SESSION_TOKEN},
    )
    # Start the existing harness without waiting for a handshake message: the
    # application raises before it can accept or close the WebSocket.
    handshake = asyncio.create_task(websocket.handshake())
    try:
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match="authentication unavailable"):
            await websocket.wait_until_closed()
        assert websocket._outgoing.empty()
    finally:
        handshake.cancel()
        await asyncio.gather(handshake, return_exceptions=True)

    manager_connect.assert_not_called()
    presence_notification.assert_not_called()
    friendship_lookup.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("delivery", ["broadcast", "send_to_user"])
async def test_failed_send_on_final_tab_still_notifies_friends_offline(
    monkeypatch, authenticated_user, presence_notification, delivery,
):
    async with connected_websocket() as websocket:
        await websocket.send_text("ready")
        await websocket.receive_json()
        presence_notification.assert_awaited_once_with(manager, 42, True)
        socket = next(iter(manager.active_connections[42]))
        failed_send = AsyncMock(side_effect=OSError("connection lost"))
        monkeypatch.setattr(socket, "send_json", failed_send)

        if delivery == "broadcast":
            await manager.broadcast("detect broken socket")
        else:
            await manager.send_to_user(42, {"type": "presence"})

        failed_send.assert_awaited_once()
        assert manager.active_connections == {}

    # The eventual endpoint disconnect must not lose the offline transition
    # already detected by failed-send cleanup.
    assert presence_notification.await_args_list == [
        call(manager, 42, True), call(manager, 42, False),
    ]


@pytest.mark.anyio
async def test_second_tab_snapshot_is_private_to_the_new_connection(
    authenticated_user, friendship_lookup, presence_notification,
):
    authenticated_user.side_effect = {
        "friend": 7, "outsider": 99, SESSION_TOKEN: 42,
    }.__getitem__
    friendship_lookup.side_effect = lambda user_id: [7] if user_id == 42 else []

    async with connected_websocket("friend") as friend:
        async with connected_websocket("outsider") as outsider:
            async with connected_websocket(online_user_ids=[7]) as first_tab:
                async with connected_websocket(online_user_ids=[7]) as new_tab:
                    # A broadcast is a barrier after snapshot creation and online
                    # notification, and exposes any extra snapshot on any tab.
                    await new_tab.send_text("all tabs ready")
                    for socket in (friend, outsider, first_tab, new_tab):
                        assert await socket.receive_json() == {
                            "type": "message", "data": {"text": "all tabs ready"},
                        }
                        assert socket._outgoing.empty()
                    assert len(manager.active_connections[42]) == 2
                    assert presence_notification.await_args_list == [
                        call(manager, 7, True), call(manager, 99, True),
                        call(manager, 42, True),
                    ]
                    assert friendship_lookup.call_args_list == [
                        call(7), call(99), call(42), call(42),
                    ]


@pytest.mark.anyio
async def test_snapshot_is_sent_after_registration_before_online_notification(
    monkeypatch, authenticated_user, presence_notification,
):
    snapshot_finished = []

    async def send_snapshot(connection_manager, socket, user_id):
        assert socket in connection_manager.active_connections[user_id]
        presence_notification.assert_not_awaited()
        await presence.send_presence_snapshot_safely(connection_manager, socket, user_id)
        snapshot_finished.append(user_id)

    def notified(connection_manager, user_id, online):
        assert connection_manager is manager
        assert snapshot_finished == [user_id]

    monkeypatch.setattr(main, "send_presence_snapshot_safely", send_snapshot)
    presence_notification.side_effect = notified
    async with connected_websocket() as websocket:
        await websocket.send_text("ready")
        assert await websocket.receive_json() == {
            "type": "message", "data": {"text": "ready"},
        }
        presence_notification.assert_awaited_once_with(manager, 42, True)


@pytest.mark.anyio
@pytest.mark.parametrize("error_type", [SQLAlchemyError, OSError])
async def test_snapshot_database_failure_is_logged_and_connection_remains_healthy(
    monkeypatch, authenticated_user, friendship_lookup, manager_connect, caplog, error_type,
):
    authenticated_user.side_effect = lambda token: 7 if token == "friend" else 42
    monkeypatch.setattr(main, "notify_presence_safely", presence.notify_presence_safely)
    # Even an OSError from the lookup must not be treated as a failed send.
    error = error_type("snapshot database lookup unavailable")

    with caplog.at_level(logging.ERROR, logger=presence.__name__):
        async with connected_websocket("friend") as friend:
            # Ensure the friend's initial notification lookup has completed.
            await friend.send_text("friend ready")
            assert await friend.receive_json() == {
                "type": "message", "data": {"text": "friend ready"},
            }
            friendship_lookup.reset_mock()
            friendship_lookup.side_effect = [error, [7], [7], []]
            async with connected_websocket(online_user_ids=None) as websocket:
                assert await friend.receive_json() == {
                    "type": "presence", "data": {"user_id": 42, "online": True},
                }
                for message in ("still healthy", "still receiving"):
                    await websocket.send_text(message)
                    for recipient in (websocket, friend):
                        assert await recipient.receive_json() == {
                            "type": "message", "data": {"text": message},
                        }
                socket = manager_connect.await_args.args[0]
                assert manager.active_connections[42] == {socket}
                assert authenticated_user.call_args_list == [call("friend"), call(SESSION_TOKEN)]
                assert not websocket._task.done()
            assert await friend.receive_json() == {
                "type": "presence", "data": {"user_id": 42, "online": False},
            }

    assert friendship_lookup.call_args_list == [call(42), call(42), call(42), call(7)]
    records = [record for record in caplog.records if record.name == presence.__name__]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].getMessage() == "Failed to send presence snapshot for user 42"
    assert records[0].exc_info[1] is error


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [OSError, WebSocketDisconnect])
@pytest.mark.parametrize("healthy_tab", [False, True], ids=["last-tab", "healthy-sibling"])
async def test_snapshot_transport_failure_exits_endpoint_without_receiving(
    monkeypatch, authenticated_user, friendship_lookup, caplog, failure, healthy_tab,
):
    authenticated_user.side_effect = lambda token: 7 if token == "friend" else 42
    friendship_lookup.side_effect = lambda user_id: [7] if user_id == 42 else []
    # Observe both cleanup and endpoint notifications through the real notifier.
    notify = AsyncMock(wraps=presence.notify_presence_safely)
    monkeypatch.setattr(main, "notify_presence_safely", notify)
    monkeypatch.setattr(presence, "notify_presence_safely", notify)
    error = failure()
    failed_send = AsyncMock(side_effect=error)
    receive = AsyncMock(side_effect=AssertionError("broken endpoint entered receive loop"))
    registered = []
    connect = manager.connect

    async def connect_broken_socket(socket, user_id):
        became_online = await connect(socket, user_id)
        assert socket in manager.active_connections[user_id]
        registered.append(socket)
        # Fail only the new socket's transport, keeping the real snapshot path.
        monkeypatch.setattr(socket, "send_json", failed_send)
        monkeypatch.setattr(socket, "receive_text", receive)
        return became_online

    async with AsyncExitStack() as stack:
        friend = await stack.enter_async_context(connected_websocket("friend"))
        await friend.send_text("friend ready")
        assert await friend.receive_json() == {
            "type": "message", "data": {"text": "friend ready"},
        }
        if healthy_tab:
            sibling = await stack.enter_async_context(connected_websocket(online_user_ids=[7]))
            assert await friend.receive_json() == {
                "type": "presence", "data": {"user_id": 42, "online": True},
            }
        surviving_connections = {
            user_id: sockets.copy() for user_id, sockets in manager.active_connections.items()
        }
        notify.reset_mock()
        friendship_lookup.reset_mock()
        monkeypatch.setattr(manager, "connect", connect_broken_socket)

        with caplog.at_level(logging.ERROR, logger=presence.__name__):
            async with connected_websocket(online_user_ids=None) as broken:
                # No client disconnect is queued: the endpoint must exit itself.
                await broken.wait_until_closed()
                assert broken._task.done()
                assert not broken._task.cancelled()
                assert broken._task.result() is None
                receive.assert_not_called()
                assert len(registered) == 1
                assert registered[0] not in manager.active_connections.get(42, set())
                assert manager.active_connections == surviving_connections
                assert broken._outgoing.empty()

        if healthy_tab:
            notify.assert_not_awaited()
            friendship_lookup.assert_called_once_with(42)
            assert not sibling._task.done()
            # Actual traffic proves the surviving endpoint remains usable.
            await sibling.send_text("healthy tab still online")
            for recipient in (sibling, friend):
                assert await recipient.receive_json() == {
                    "type": "message", "data": {"text": "healthy tab still online"},
                }
            assert manager.active_connections == surviving_connections
            assert not sibling._task.done()
        else:
            notify.assert_awaited_once_with(manager, 42, False)
            assert friendship_lookup.call_args_list == [call(42), call(42)]
            assert await friend.receive_json() == {
                "type": "presence", "data": {"user_id": 42, "online": False},
            }
        assert friend._outgoing.empty()
        failed_send.assert_awaited_once_with({
            "type": "presence_snapshot", "data": {"online_user_ids": [7]},
        })

    records = [record for record in caplog.records if record.name == presence.__name__]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].getMessage() == "Failed to send presence snapshot for user 42"
    assert records[0].exc_info[1] is error
