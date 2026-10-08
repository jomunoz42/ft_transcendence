"""Tests for the anonymous in-memory WebSocket transport.

The ASGI harness keeps every client on one event loop, making assertions about
the process-wide connection manager deterministic.
"""

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from fastapi import WebSocketDisconnect

from app.main import ConnectionManager, app, manager


class ASGIWebSocketSession:
    """Drive one WebSocket connection through the FastAPI ASGI application."""

    def __init__(self, path="/ws"):
        self._incoming = asyncio.Queue()
        self._outgoing = asyncio.Queue()
        self._task = None
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
            "headers": [],
            "subprotocols": [],
            "state": {},
            "extensions": {},
        }

    async def connect(self):
        self._task = asyncio.create_task(
            app(self._scope, self._incoming.get, self._outgoing.put)
        )
        await self._incoming.put({"type": "websocket.connect"})
        assert await self._receive() == {
            "type": "websocket.accept",
            "subprotocol": None,
            "headers": [],
        }

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
    websocket = ASGIWebSocketSession()
    await websocket.connect()
    try:
        yield websocket
    finally:
        await websocket.disconnect()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def websocket_connection_state_does_not_leak_between_tests():
    """Every transport test must leave the process-wide manager empty."""
    assert manager.active_connections == []
    yield
    assert manager.active_connections == []


@pytest.mark.anyio
async def test_client_can_connect_and_is_removed_when_it_disconnects():
    async with connected_websocket():
        assert len(manager.active_connections) == 1

    assert manager.active_connections == []


@pytest.mark.anyio
async def test_broadcast_reaches_all_clients_including_the_sender():
    expected_event = {"type": "message", "data": {"text": "hello everyone"}}

    async with connected_websocket() as sender:
        async with connected_websocket() as recipient:
            assert len(manager.active_connections) == 2

            await sender.send_text("hello everyone")

            assert await sender.receive_json() == expected_event
            assert await recipient.receive_json() == expected_event


@pytest.mark.anyio
async def test_remaining_client_keeps_receiving_after_another_disconnects():
    expected_event = {"type": "message", "data": {"text": "still here"}}

    async with connected_websocket() as remaining_client:
        async with connected_websocket():
            assert len(manager.active_connections) == 2

        assert len(manager.active_connections) == 1
        await remaining_client.send_text("still here")
        assert await remaining_client.receive_json() == expected_event


@pytest.mark.anyio
async def test_unexpected_endpoint_error_still_removes_connection(monkeypatch):
    async def fail_to_broadcast(_message):
        raise RuntimeError("unexpected broadcast failure")

    monkeypatch.setattr(manager, "broadcast", fail_to_broadcast)
    websocket = ASGIWebSocketSession()
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
