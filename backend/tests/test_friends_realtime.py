"""Friend routes refresh presence on open WebSockets right after the commit, with the 5 s polling turned off."""

from contextlib import AsyncExitStack
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.auth.constants import SESSION_COOKIE_NAME
from app.db import get_session
from app.main import app, manager
from test_realtime_lifecycle import connected, realtime, snapshot
from test_websocket_postgres import postgres_sessions

pytestmark = pytest.mark.anyio

FRIENDS = "/api/v1/friends"


async def receive_presence(socket):
    """Persistent notifications may precede the existing presence refresh."""
    while True:
        event = await socket.receive_json()
        if event["type"] != "notification":
            return event


@pytest.fixture
def no_polling(realtime, monkeypatch):
    """The realtime app with the friendship polling pushed out of reach, so only a notification can refresh."""
    monkeypatch.setattr(manager, "FRIENDSHIP_REFRESH_INTERVAL", 60)
    return realtime


async def call(method, path, token):
    """Send one friend route as the user who owns token; a server error comes back as a 500 response."""
    transport = httpx.ASGITransport(app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as http:
        return await http.request(method, f"{FRIENDS}{path}", headers={"cookie": f"{SESSION_COOKIE_NAME}={token}"})


async def test_accepting_a_request_refreshes_both_sides(no_polling):
    factory, tokens, ids = no_polling
    async with AsyncExitStack() as stack:
        sender = await stack.enter_async_context(connected(tokens[0]))
        addressee = await stack.enter_async_context(connected(tokens[2]))

        response = await call("POST", f"/accept/{ids[0]}", tokens[2])

        assert response.status_code == 200
        assert await receive_presence(sender) == snapshot([ids[2]])
        assert await receive_presence(addressee) == snapshot([ids[0]])


async def test_asking_back_refreshes_both_sides(no_polling):
    factory, tokens, ids = no_polling
    async with AsyncExitStack() as stack:
        first_asker = await stack.enter_async_context(connected(tokens[0]))
        asker_back = await stack.enter_async_context(connected(tokens[2]))

        response = await call("POST", f"/request/{ids[0]}", tokens[2])

        assert response.json() == {"status": "accepted"}
        assert await receive_presence(first_asker) == snapshot([ids[2]])
        assert await receive_presence(asker_back) == snapshot([ids[0]])


@pytest.mark.parametrize(("method", "route"), [("DELETE", "/{them}"), ("POST", "/block/{them}")])
async def test_ending_a_friendship_refreshes_both_sides(no_polling, method, route):
    factory, tokens, ids = no_polling
    async with AsyncExitStack() as stack:
        friend = await stack.enter_async_context(connected(tokens[1]))
        me = await stack.enter_async_context(connected(tokens[0], [ids[1]]))
        await receive_presence(friend)  # I came online.

        response = await call(method, route.format(them=ids[1]), tokens[0])

        assert response.status_code == 200
        assert await receive_presence(me) == snapshot([])
        assert await receive_presence(friend) == snapshot([])


async def test_every_open_tab_gets_the_refresh(no_polling):
    factory, tokens, ids = no_polling
    async with AsyncExitStack() as stack:
        first_tab = await stack.enter_async_context(connected(tokens[0]))
        second_tab = await stack.enter_async_context(connected(tokens[0]))
        addressee = await stack.enter_async_context(connected(tokens[2]))

        await call("POST", f"/accept/{ids[0]}", tokens[2])

        assert await receive_presence(first_tab) == snapshot([ids[2]])
        assert await receive_presence(second_tab) == snapshot([ids[2]])
        assert await receive_presence(addressee) == snapshot([ids[0]])


async def test_a_refused_action_sends_nothing(no_polling, monkeypatch):
    factory, tokens, ids = no_polling
    schedule = Mock(wraps=manager.schedule_snapshot)
    monkeypatch.setattr(manager, "schedule_snapshot", schedule)

    response = await call("POST", f"/accept/{ids[2]}", tokens[0])

    assert response.status_code == 404
    schedule.assert_not_called()


async def test_a_failed_commit_sends_nothing(no_polling, monkeypatch):
    factory, tokens, ids = no_polling
    schedule = Mock(wraps=manager.schedule_snapshot)
    monkeypatch.setattr(manager, "schedule_snapshot", schedule)

    def failing_session():
        with factory() as session:
            session.commit = Mock(side_effect=SQLAlchemyError("commit failed"))
            yield session

    app.dependency_overrides[get_session] = failing_session
    response = await call("POST", f"/accept/{ids[0]}", tokens[2])

    assert response.status_code == 500
    schedule.assert_not_called()


async def test_a_broken_notification_keeps_the_answer_and_logs(no_polling, monkeypatch, caplog):
    factory, tokens, ids = no_polling
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(connected(tokens[0]))
        monkeypatch.setattr(manager, "schedule_snapshot", Mock(side_effect=RuntimeError("queue gone")))

        response = await call("POST", f"/accept/{ids[0]}", tokens[2])

        assert (response.status_code, response.json()) == (200, {"status": "accepted"})
        assert "Realtime friendship notification failed" in caplog.text
