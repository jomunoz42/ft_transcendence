"""Committed actions through real HTTP, PostgreSQL, and authenticated WebSockets."""

import asyncio
from contextlib import AsyncExitStack
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select

from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.sessions import end_session, start_session
from app.db.models import Friendship, Notification, Top10Reaction, User
from app.main import app, manager
from test_realtime_lifecycle import connected, realtime
from test_websocket_postgres import postgres_sessions

pytestmark = pytest.mark.anyio


@pytest.fixture
async def notifications_realtime(realtime, monkeypatch):
    monkeypatch.setattr(manager, "SESSION_REVALIDATE_INTERVAL", 60)
    monkeypatch.setattr(manager, "FRIENDSHIP_REFRESH_INTERVAL", 60)
    return realtime


async def call(token, method, path, **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app, raise_app_exceptions=False), base_url="https://testserver") as http:
        return await http.request(method, "/api/v1" + path, headers={"cookie": f"{SESSION_COOKIE_NAME}={token}"}, **kwargs)


async def request_friend(tokens, ids):
    return await call(tokens[1], "POST", f"/friends/request/{ids[2]}")


def stored(factory):
    with factory() as session:
        return session.scalars(select(Notification).order_by(Notification.id)).all()


async def test_online_delivery_targets_every_recipient_session_only_after_commit(notifications_realtime, monkeypatch):
    factory, tokens, ids = notifications_realtime
    with factory.begin() as session:
        second_token = start_session(session, session.get(User, ids[2]))
    send = manager.send_to_user
    checked = []

    async def check_commit(recipient_id, event):
        # An independent connection can only see committed notification/action rows.
        with factory() as session:
            notification = session.get(Notification, event["data"]["id"])
            assert notification is not None
            assert notification.recipient_id == recipient_id
            assert session.scalar(select(Friendship).where(Friendship.requester_id == ids[1], Friendship.addressee_id == ids[2])) is not None
        checked.append(event)
        await send(recipient_id, event)

    async with AsyncExitStack() as stack:
        actor = await stack.enter_async_context(connected(tokens[1]))
        outsider = await stack.enter_async_context(connected(tokens[3]))
        first = await stack.enter_async_context(connected(tokens[2]))
        second = await stack.enter_async_context(connected(second_token))
        monkeypatch.setattr(manager, "send_to_user", check_commit)
        response = await request_friend(tokens, ids)
        assert response.status_code == 200
        notification = stored(factory)[0]
        event = {"type": "notification", "data": {"id": notification.id}}
        assert checked == [event]
        assert await first.receive_json() == event
        assert await second.receive_json() == event
        assert actor._outgoing.empty()
        assert outsider._outgoing.empty()

        assert (await request_friend(tokens, ids)).status_code == 200
        assert len(stored(factory)) == 1
        assert checked == [event]
        assert first._outgoing.empty() and second._outgoing.empty()


async def test_offline_recipient_reads_persisted_notification_after_reconnect(notifications_realtime):
    factory, tokens, ids = notifications_realtime
    assert (await request_friend(tokens, ids)).status_code == 200
    notification = stored(factory)[0]
    response = await call(tokens[2], "GET", "/notifications")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [notification.id]
    assert (await call(tokens[2], "GET", "/notifications/unread-count")).json() == {"unread_count": 1}
    assert (await call(tokens[1], "GET", "/notifications")).json() == []
    async with connected(tokens[2]) as socket:
        # Reconnect uses the existing presence handshake; clients resync via REST.
        assert socket._outgoing.empty()
        assert (await call(tokens[2], "GET", "/notifications")).json()[0]["id"] == notification.id


async def test_delivery_exception_does_not_fail_committed_action(notifications_realtime, monkeypatch, caplog):
    factory, tokens, ids = notifications_realtime
    monkeypatch.setattr(manager, "send_to_user", AsyncMock(side_effect=RuntimeError("private transport detail")))
    response = await request_friend(tokens, ids)
    assert response.status_code == 200
    assert len(stored(factory)) == 1
    with factory() as session:
        assert session.scalar(select(Friendship).where(Friendship.requester_id == ids[1], Friendship.addressee_id == ids[2])) is not None
    assert "Realtime notification delivery failed" in caplog.text
    assert "private transport detail" not in caplog.text
    assert len((await call(tokens[2], "GET", "/notifications")).json()) == 1


async def test_broken_socket_does_not_prevent_other_session_delivery(notifications_realtime, monkeypatch):
    factory, tokens, ids = notifications_realtime
    async with AsyncExitStack() as stack:
        broken = await stack.enter_async_context(connected(tokens[2]))
        broken_server = next(iter(manager.active_connections[ids[2]]))
        healthy = await stack.enter_async_context(connected(tokens[2]))
        monkeypatch.setattr(broken_server, "send_json", AsyncMock(side_effect=OSError("socket failed")))
        assert (await request_friend(tokens, ids)).status_code == 200
        notification = stored(factory)[0]
        assert await healthy.receive_json() == {"type": "notification", "data": {"id": notification.id}}
        close = await broken._receive()
        assert close["type"] == "websocket.close"
        await broken.wait_until_closed()
        assert len(manager.active_connections[ids[2]]) == 1


async def test_revoked_socket_gets_no_notification_while_other_login_receives_it(notifications_realtime):
    factory, tokens, ids = notifications_realtime
    with factory.begin() as session:
        second_token = start_session(session, session.get(User, ids[2]))
    async with AsyncExitStack() as stack:
        revoked = await stack.enter_async_context(connected(tokens[2]))
        healthy = await stack.enter_async_context(connected(second_token))
        with factory.begin() as session:
            end_session(session, tokens[2])
        assert (await request_friend(tokens, ids)).status_code == 200
        assert (await revoked._receive())["type"] == "websocket.close"
        await revoked.wait_until_closed()
        assert revoked._outgoing.empty()
        assert (await healthy.receive_json())["type"] == "notification"


async def test_concurrent_reaction_update_retries_produce_one_event(notifications_realtime):
    factory, tokens, ids = notifications_realtime
    path = f"/profiles/{ids[0]}/reactions"
    assert (await call(tokens[1], "POST", path, json={"reaction": "like"})).status_code == 200
    responses = await asyncio.gather(*[
        call(tokens[1], "POST", path, json={"reaction": "dislike"}) for _ in range(2)
    ])
    assert all(response.status_code == 200 for response in responses)
    assert [row.event_type for row in stored(factory)] == ["reaction.created", "reaction.updated"]
    with factory() as session:
        assert session.scalars(select(Top10Reaction)).one().reaction == "dislike"
