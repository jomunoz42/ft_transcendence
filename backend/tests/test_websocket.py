"""Tests for the authenticated in-memory WebSocket transport.

The ASGI harness keeps every client on one event loop, making assertions about
the process-wide connection manager deterministic.
"""

import asyncio
import json
import threading
from contextlib import asynccontextmanager
from http.cookies import SimpleCookie
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import WebSocketDisconnect

import app.main as main
import app.auth.websocket as websocket_auth
from app.auth.constants import SESSION_COOKIE_NAME
from app.main import ConnectionManager, app, manager

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
async def connected_websocket():
    websocket = ASGIWebSocketSession(
        headers={"origin": ALLOWED_ORIGIN},
        cookies={SESSION_COOKIE_NAME: SESSION_TOKEN},
    )
    await websocket.connect()
    try:
        yield websocket
    finally:
        await websocket.disconnect()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def forbid_database_access(monkeypatch):
    """Endpoint tests must never reach the configured database."""
    factory = Mock(side_effect=AssertionError("unexpected database access"))
    monkeypatch.setattr(websocket_auth, "SessionLocal", factory)
    return factory


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
    assert manager.active_connections == []
    yield
    assert manager.active_connections == []


@pytest.mark.anyio
async def test_client_can_connect_and_is_removed_when_it_disconnects(authenticated_user):
    async with connected_websocket():
        assert len(manager.active_connections) == 1

    assert manager.active_connections == []
    authenticated_user.assert_called_once_with(SESSION_TOKEN)


@pytest.mark.anyio
async def test_broadcast_reaches_all_clients_including_the_sender(authenticated_user):
    expected_event = {"type": "message", "data": {"text": "hello everyone"}}

    async with connected_websocket() as sender:
        async with connected_websocket() as recipient:
            assert len(manager.active_connections) == 2

            await sender.send_text("hello everyone")

            assert await sender.receive_json() == expected_event
            assert await recipient.receive_json() == expected_event


@pytest.mark.anyio
async def test_remaining_client_keeps_receiving_after_another_disconnects(authenticated_user):
    expected_event = {"type": "message", "data": {"text": "still here"}}

    async with connected_websocket() as remaining_client:
        async with connected_websocket():
            assert len(manager.active_connections) == 2

        assert len(manager.active_connections) == 1
        await remaining_client.send_text("still here")
        assert await remaining_client.receive_json() == expected_event


@pytest.mark.anyio
async def test_unexpected_endpoint_error_still_removes_connection(monkeypatch, authenticated_user):
    async def fail_to_broadcast(_message):
        raise RuntimeError("unexpected broadcast failure")

    monkeypatch.setattr(manager, "broadcast", fail_to_broadcast)
    websocket = ASGIWebSocketSession(
        headers={"origin": ALLOWED_ORIGIN},
        cookies={SESSION_COOKIE_NAME: SESSION_TOKEN},
    )
    await websocket.connect()
    await websocket.send_text("trigger failure")

    with pytest.raises(RuntimeError, match="unexpected broadcast failure"):
        await websocket.wait_until_closed()

    assert manager.active_connections == []


@pytest.mark.anyio
async def test_broadcast_removes_disconnected_client_and_continues():
    local_manager = ConnectionManager()
    delivered_events = []

    class DisconnectedClient:
        async def send_json(self, _event):
            raise WebSocketDisconnect()

    class ConnectedClient:
        async def send_json(self, event):
            delivered_events.append(event)

    disconnected_client = DisconnectedClient()
    connected_client = ConnectedClient()
    local_manager.active_connections = [disconnected_client, connected_client]

    await local_manager.broadcast("delivered")
    local_manager.disconnect(disconnected_client)

    assert local_manager.active_connections == [connected_client]
    assert delivered_events == [
        {"type": "message", "data": {"text": "delivered"}}
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("origin", [
    None, "null", "https://evil.example", "http://localhost:5173.evil.example",
    "http://localhost:5174", "https://localhost:5173",
])
async def test_unauthorized_origin_is_rejected_before_authentication(
    origin, authenticated_user, manager_connect, forbid_database_access,
):
    websocket = ASGIWebSocketSession(
        headers={} if origin is None else {"origin": origin},
        cookies={SESSION_COOKIE_NAME: SESSION_TOKEN},
    )

    await websocket.assert_rejected()

    authenticated_user.assert_not_called()
    forbid_database_access.assert_not_called()
    manager_connect.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("cookies", [
    {}, {SESSION_COOKIE_NAME: ""}, {"session": SESSION_TOKEN},
])
async def test_missing_cookie_is_rejected_before_authentication(
    cookies, authenticated_user, manager_connect, forbid_database_access,
):
    websocket = ASGIWebSocketSession(
        headers={"origin": ALLOWED_ORIGIN}, cookies=cookies,
    )

    await websocket.assert_rejected()

    authenticated_user.assert_not_called()
    forbid_database_access.assert_not_called()
    manager_connect.assert_not_called()


@pytest.mark.anyio
async def test_invalid_authentication_never_enters_connection_manager(
    authenticated_user, manager_connect,
):
    authenticated_user.return_value = None
    websocket = ASGIWebSocketSession(
        headers={"origin": ALLOWED_ORIGIN},
        cookies={SESSION_COOKIE_NAME: SESSION_TOKEN},
    )

    await websocket.assert_rejected()

    authenticated_user.assert_called_once_with(SESSION_TOKEN)
    manager_connect.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("origin", [ALLOWED_ORIGIN, "http://127.0.0.1:5173"])
async def test_authentication_runs_in_threadpool_before_accepting(
    monkeypatch, origin, manager_connect,
):
    event_loop_thread = threading.get_ident()

    def authenticate(token):
        assert token == SESSION_TOKEN
        assert threading.get_ident() != event_loop_thread
        assert manager.active_connections == []
        manager_connect.assert_not_called()
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
        await websocket.send_text("authenticated 🎵")
        assert await websocket.receive_json() == {
            "type": "message", "data": {"text": "authenticated 🎵"}
        }
    finally:
        await websocket.disconnect()
