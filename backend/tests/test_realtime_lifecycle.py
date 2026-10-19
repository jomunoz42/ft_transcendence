"""Committed PostgreSQL sessions/friendships through real HTTP and WebSockets."""

import asyncio
import datetime
import threading
from contextlib import AsyncExitStack, asynccontextmanager
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

import app.realtime.manager as realtime_manager
from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.sessions import end_session, start_session
from app.db import get_session
from app.db.friendships import send_friend_request
from app.db.models import User, UserSession
from app.main import app, manager
from test_websocket_postgres import client, postgres_sessions

pytestmark = pytest.mark.anyio


@pytest.fixture
async def realtime(postgres_sessions, monkeypatch):
    factory, tokens, ids = postgres_sessions
    monkeypatch.setattr(manager, "SESSION_REVALIDATE_INTERVAL", 0.03)
    monkeypatch.setattr(manager, "FRIENDSHIP_REFRESH_INTERVAL", 0.03)

    def request_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = request_session
    try:
        async with app.router.lifespan_context(app):
            yield factory, tokens, ids
    finally:
        app.dependency_overrides.clear()
    assert manager.active_connections == {}
    assert manager.session_tokens == {}
    assert manager.friend_ids == {}
    assert manager.snapshot_pending == {}
    assert manager.disconnected == {}


@asynccontextmanager
async def connected(token, online=()):
    socket = client(token)
    await socket.connect()
    try:
        assert await socket.receive_json() == snapshot(online)
        yield socket
    finally:
        await socket.disconnect()


def snapshot(ids=()):
    return {"type": "presence_snapshot", "data": {"online_user_ids": sorted(ids)}}


def presence(user_id, online):
    return {"type": "presence", "data": {"user_id": user_id, "online": online}}


async def closed(socket, code=1008):
    assert await socket._receive() == {"type": "websocket.close", "code": code, "reason": ""}
    await socket.wait_until_closed()
    assert socket._outgoing.empty()


async def logout(token):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://testserver") as http:
        response = await http.post("/api/v1/auth/logout", headers={"cookie": f"{SESSION_COOKIE_NAME}={token}"})
    assert response.status_code == 204
    return response


async def test_http_logout_closes_all_session_tabs_but_preserves_other_login(realtime, monkeypatch):
    monkeypatch.setattr(manager, "SESSION_REVALIDATE_INTERVAL", 60)
    monkeypatch.setattr(manager, "FRIENDSHIP_REFRESH_INTERVAL", 60)
    factory, tokens, ids = realtime
    with factory.begin() as session:
        other_token = start_session(session, session.get(User, ids[0]))
    async with AsyncExitStack() as stack:
        friend = await stack.enter_async_context(connected(tokens[1]))
        first = await stack.enter_async_context(connected(tokens[0], [ids[1]]))
        assert await friend.receive_json() == presence(ids[0], True)
        second = await stack.enter_async_context(connected(tokens[0], [ids[1]]))
        other_login = await stack.enter_async_context(connected(other_token, [ids[1]]))
        outsider = await stack.enter_async_context(connected(tokens[3]))
        await logout(tokens[0])
        await asyncio.gather(closed(first), closed(second))
        assert len(manager.active_connections[ids[0]]) == 1
        assert not other_login._task.done()
        assert friend._outgoing.empty()
        await client(tokens[0]).assert_rejected()
        await logout(other_token)
        await closed(other_login)
        assert await friend.receive_json() == presence(ids[0], False)
        assert friend._outgoing.empty()
        assert outsider._outgoing.empty()


@pytest.mark.parametrize("state", ["revoked", "expired", "deleted"])
async def test_idle_socket_rechecks_database_session(realtime, monkeypatch, state):
    monkeypatch.setattr(manager, "FRIENDSHIP_REFRESH_INTERVAL", 60)
    factory, tokens, ids = realtime
    async with connected(tokens[0]) as socket:
        with factory.begin() as session:
            if state == "revoked":
                end_session(session, tokens[0])
            elif state == "expired":
                stored = session.query(UserSession).filter_by(user_id=ids[0]).one()
                stored.expires_at = func.now() - datetime.timedelta(seconds=1)
            else:
                session.get(User, ids[0]).deleted_at = func.now()
        await closed(socket)
        assert ids[0] not in manager.active_connections


async def test_outbound_delivery_revalidates_before_idle_poll(realtime, monkeypatch):
    factory, tokens, ids = realtime
    monkeypatch.setattr(manager, "SESSION_REVALIDATE_INTERVAL", 60)
    async with connected(tokens[0]) as socket:
        with factory.begin() as session:
            end_session(session, tokens[0])
        await manager.send_to_user(ids[0], presence(ids[1], True))
        # Inspect the close immediately, without waiting for the idle deadline.
        assert await socket._receive() == {"type": "websocket.close", "code": 1008, "reason": ""}
        assert socket._outgoing.empty()
        assert ids[0] not in manager.active_connections


async def test_logout_between_handshake_authentication_and_snapshot_is_rechecked(realtime, monkeypatch):
    factory, tokens, ids = realtime
    original = manager.connect

    async def connect_then_revoke(socket, user_id):
        result = await original(socket, user_id)
        with factory.begin() as session:
            end_session(session, tokens[0])
        return result

    monkeypatch.setattr(manager, "connect", connect_then_revoke)
    socket = client(tokens[0])
    await socket.connect()
    await closed(socket)
    assert manager.active_connections == {}


async def test_continuous_client_frames_cannot_defer_revocation(realtime):
    factory, tokens, ids = realtime
    async with connected(tokens[0]) as socket:
        async def chatter():
            while not socket._task.done():
                await socket.send_text("ignored")
                await asyncio.sleep(0.001)
        traffic = asyncio.create_task(chatter())
        try:
            with factory.begin() as session:
                end_session(session, tokens[0])
            await closed(socket)
        finally:
            traffic.cancel()
            await asyncio.gather(traffic, return_exceptions=True)


@pytest.mark.parametrize("failure", ["database", "timeout"])
@pytest.mark.parametrize("delivery", ["poll", "outbound"])
async def test_revalidation_failure_closes_without_payload_or_token_logging(realtime, monkeypatch, caplog, failure, delivery):
    factory, tokens, ids = realtime
    if delivery == "outbound":
        monkeypatch.setattr(manager, "SESSION_REVALIDATE_INTERVAL", 60)
    async with connected(tokens[0]) as socket:
        async def unavailable(function, token):
            if failure == "database":
                raise SQLAlchemyError("database unavailable")
            await asyncio.Event().wait()
        monkeypatch.setattr(realtime_manager, "run_in_threadpool", unavailable)
        monkeypatch.setattr(realtime_manager, "DB_TIMEOUT", 0.01)
        if delivery == "outbound":
            await manager.send_to_user(ids[0], presence(ids[1], True))
        await closed(socket, 1011)
        assert tokens[0] not in caplog.text
        assert "session revalidation unavailable" in caplog.text
        assert ids[0] not in manager.active_connections


async def test_friend_acceptance_refreshes_both_users_and_tabs_only_after_commit(realtime):
    factory, tokens, ids = realtime
    async with AsyncExitStack() as stack:
        requester = await stack.enter_async_context(connected(tokens[0]))
        requester_tab = await stack.enter_async_context(connected(tokens[0]))
        addressee = await stack.enter_async_context(connected(tokens[2]))
        addressee_tab = await stack.enter_async_context(connected(tokens[2]))
        outsider = await stack.enter_async_context(connected(tokens[3]))
        with factory() as session:
            accepted = send_friend_request(session, ids[2], ids[0])
            assert accepted.status == "accepted"
            # Force a reconciliation while the acceptance is uncommitted.
            for user_id in (ids[0], ids[2], ids[3]):
                for socket in manager.active_connections[user_id].copy():
                    manager.schedule_snapshot(socket, user_id)
            await asyncio.wait_for(manager.presence_queue.join(), 1)
            for socket in (requester, requester_tab, addressee, addressee_tab, outsider):
                assert socket._outgoing.empty()
            session.commit()
        for socket in (requester, requester_tab):
            assert await socket.receive_json() == snapshot([ids[2]])
        for socket in (addressee, addressee_tab):
            assert await socket.receive_json() == snapshot([ids[0]])
        assert outsider._outgoing.empty()
        # An unchanged friendship set never generates duplicate snapshots.
        for user_id in (ids[0], ids[2], ids[3]):
            for socket in manager.active_connections[user_id].copy():
                manager.schedule_snapshot(socket, user_id)
        await asyncio.wait_for(manager.presence_queue.join(), 1)
        for socket in (requester, requester_tab, addressee, addressee_tab, outsider):
            assert socket._outgoing.empty()


async def test_acceptance_with_offline_friend_and_later_connect(realtime):
    factory, tokens, ids = realtime
    async with connected(tokens[0]) as requester:
        with factory.begin() as session:
            send_friend_request(session, ids[2], ids[0])
        # The refreshed snapshot deliberately contains no offline IDs.
        assert await requester.receive_json() == snapshot()
        async with connected(tokens[2], [ids[0]]):
            assert await requester.receive_json() == presence(ids[2], True)
        assert await requester.receive_json() == presence(ids[2], False)


async def test_rolled_back_acceptance_does_not_refresh_presence(realtime):
    factory, tokens, ids = realtime
    async with connected(tokens[0]) as requester:
        async with connected(tokens[2]) as addressee:
            with factory() as session:
                send_friend_request(session, ids[2], ids[0])
                session.rollback()
            for user_id in (ids[0], ids[2]):
                for socket in manager.active_connections[user_id].copy():
                    manager.schedule_snapshot(socket, user_id)
            await asyncio.wait_for(manager.presence_queue.join(), 1)
            assert requester._outgoing.empty()
            assert addressee._outgoing.empty()


async def test_friend_deletion_refresh_removes_deleted_online_account(realtime):
    factory, tokens, ids = realtime
    async with connected(tokens[1]) as friend:
        async with connected(tokens[0], [ids[1]]) as subject:
            assert await friend.receive_json() == presence(ids[0], True)
            with factory.begin() as session:
                session.get(User, ids[1]).deleted_at = func.now()
            await closed(friend)
            # A concurrent offline transition may arrive before the replacement.
            while True:
                event = await subject.receive_json()
                if event["type"] == "presence_snapshot":
                    assert event == snapshot()
                    break
                assert event == presence(ids[1], False)


async def test_missing_session_binding_fails_closed(realtime):
    factory, tokens, ids = realtime
    async with connected(tokens[0]) as socket:
        transport = next(iter(manager.active_connections[ids[0]]))
        manager.session_tokens.pop(transport)
        await manager.send_to_user(ids[0], presence(ids[1], True))
        await closed(socket)
        assert ids[0] not in manager.active_connections


async def test_logout_notification_runs_on_event_loop_after_commit(realtime, monkeypatch):
    factory, tokens, ids = realtime
    loop_thread = threading.get_ident()
    original = manager.disconnect_session
    observed = []

    async def notify(token):
        assert threading.get_ident() == loop_thread
        # A separate DB transaction sees the committed deletion.
        with factory() as session:
            assert session.query(UserSession).filter_by(user_id=ids[0]).count() == 0
        observed.append(token)
        await original(token)

    monkeypatch.setattr(manager, "disconnect_session", notify)
    async with connected(tokens[0]) as socket:
        await logout(tokens[0])
        assert observed == [tokens[0]]
        await closed(socket)


async def test_failed_logout_commit_never_notifies_or_disconnects(realtime, monkeypatch):
    factory, tokens, ids = realtime
    notify = AsyncMock(wraps=manager.disconnect_session)
    monkeypatch.setattr(manager, "disconnect_session", notify)

    def failing_session():
        with factory() as session:
            session.commit = Mock(side_effect=SQLAlchemyError("commit failed"))
            yield session

    async with connected(tokens[0]) as socket:
        app.dependency_overrides[get_session] = failing_session
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app, raise_app_exceptions=False),
            base_url="https://testserver",
        ) as http:
            response = await http.post("/api/v1/auth/logout", headers={"cookie": f"{SESSION_COOKIE_NAME}={tokens[0]}"})
        assert response.status_code == 500
        notify.assert_not_awaited()
        assert not socket._task.done()
        # Rollback left this session valid, including for protected delivery.
        await manager.send_to_user(ids[0], presence(ids[1], True))
        assert await socket.receive_json() == presence(ids[1], True)


@pytest.mark.parametrize("fallback", ["poll", "outbound"])
async def test_notification_failure_preserves_logout_and_security_fallback(realtime, monkeypatch, caplog, fallback):
    factory, tokens, ids = realtime
    monkeypatch.setattr(manager, "FRIENDSHIP_REFRESH_INTERVAL", 60)
    if fallback == "outbound":
        monkeypatch.setattr(manager, "SESSION_REVALIDATE_INTERVAL", 60)
    notify = AsyncMock(side_effect=RuntimeError(tokens[0]))
    monkeypatch.setattr(manager, "disconnect_session", notify)
    async with connected(tokens[0]) as socket:
        response = await logout(tokens[0])
        assert "Max-Age=0" in response.headers["set-cookie"]
        notify.assert_awaited_once_with(tokens[0])
        if fallback == "outbound":
            await manager.send_to_user(ids[0], presence(ids[1], True))
        await closed(socket)
        assert tokens[0] not in caplog.text
        assert "Realtime logout notification failed" in caplog.text


async def test_logout_notification_before_socket_registration_cannot_be_missed(realtime, monkeypatch):
    factory, tokens, ids = realtime
    started, release = asyncio.Event(), asyncio.Event()
    original = manager.connect

    async def delayed_connect(socket, user_id):
        started.set()  # The handshake DB lookup has already succeeded.
        await release.wait()
        return await original(socket, user_id)

    monkeypatch.setattr(manager, "connect", delayed_connect)
    socket = client(tokens[0])
    handshake = asyncio.create_task(socket.connect())
    try:
        await asyncio.wait_for(started.wait(), 1)
        await logout(tokens[0])
        assert manager.active_connections == {}
        release.set()
        await handshake
        await closed(socket)  # No snapshot was delivered with the stale lookup.
    finally:
        release.set()
        await asyncio.gather(handshake, return_exceptions=True)
        await socket.disconnect()


async def test_logout_wakes_initialization_without_waiting_for_snapshot_query(realtime, monkeypatch):
    factory, tokens, ids = realtime
    started, release = asyncio.Event(), asyncio.Event()
    original = realtime_manager.send_presence_snapshot_safely

    async def delayed_snapshot(manager, socket, user_id):
        started.set()
        await release.wait()
        return await original(manager, socket, user_id)

    monkeypatch.setattr(realtime_manager, "send_presence_snapshot_safely", delayed_snapshot)
    socket = client(tokens[0])
    await socket.connect()
    try:
        await asyncio.wait_for(started.wait(), 1)
        await logout(tokens[0])
        await closed(socket)
        assert manager.snapshot_pending == {}
    finally:
        release.set()
        await asyncio.wait_for(manager.presence_queue.join(), 1)
        await socket.disconnect()
    assert socket._outgoing.empty()


async def test_logout_during_outbound_validation_discards_its_stale_result(realtime, monkeypatch):
    factory, tokens, ids = realtime
    monkeypatch.setattr(manager, "SESSION_REVALIDATE_INTERVAL", 60)
    monkeypatch.setattr(manager, "FRIENDSHIP_REFRESH_INTERVAL", 60)
    original = realtime_manager.run_in_threadpool
    checked, release = asyncio.Event(), asyncio.Event()
    async with connected(tokens[0]) as socket:
        transport = next(iter(manager.active_connections[ids[0]]))
        removed = manager.disconnected[transport]

        async def delayed_result(function, token):
            result = await original(function, token)
            checked.set()  # This valid result predates logout's commit.
            await release.wait()
            return result

        monkeypatch.setattr(realtime_manager, "run_in_threadpool", delayed_result)
        sending = asyncio.create_task(manager.send_to_user(ids[0], presence(ids[1], True)))
        logging_out = None
        try:
            await asyncio.wait_for(checked.wait(), 1)
            logging_out = asyncio.create_task(logout(tokens[0]))
            await asyncio.wait_for(removed.wait(), 1)
            assert ids[0] not in manager.active_connections
            # The notifier waits for this socket's send lock before closing it.
            release.set()
            await asyncio.wait_for(sending, 1)
            await asyncio.wait_for(logging_out, 1)
            await closed(socket)
        finally:
            release.set()
            await asyncio.gather(sending, *([logging_out] if logging_out else []), return_exceptions=True)


async def test_friendship_refresh_is_independent_of_session_polling(realtime, monkeypatch):
    factory, tokens, ids = realtime
    monkeypatch.setattr(manager, "SESSION_REVALIDATE_INTERVAL", 60)
    revalidate = AsyncMock(wraps=manager.revalidate)
    monkeypatch.setattr(manager, "revalidate", revalidate)
    async with connected(tokens[0]) as requester:
        async with connected(tokens[2]) as addressee:
            with factory.begin() as session:
                send_friend_request(session, ids[2], ids[0])
            assert await requester.receive_json() == snapshot([ids[2]])
            assert await addressee.receive_json() == snapshot([ids[0]])
            revalidate.assert_not_awaited()
