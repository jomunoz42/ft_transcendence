"""Opt-in through a PostgreSQL DATABASE_URL; each test owns a temporary schema.

These exercise committed sessions across the real handshake/threadpool boundary,
not a mocked authentication result. They do not replace migration tests.
"""

import asyncio
import datetime
import uuid

import pytest
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

import app.auth.websocket as websocket_auth
import app.realtime.presence as presence
from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.sessions import end_session, start_session
from app.db import engine
from app.db.models import Base, Friendship, User, UserSession
from app.main import app, manager
from test_websocket import ALLOWED_ORIGIN, ASGIWebSocketSession

pytestmark = pytest.mark.anyio


@pytest.fixture
def postgres_sessions(monkeypatch):
    if engine.dialect.name != "postgresql":
        pytest.skip("requires a running PostgreSQL server via DATABASE_URL")
    schema = "test_realtime_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(isolated)
        factory = sessionmaker(bind=isolated, expire_on_commit=False)
        monkeypatch.setattr(websocket_auth, "SessionLocal", factory)
        monkeypatch.setattr(presence, "SessionLocal", factory)
        tokens, ids = [], []
        with factory.begin() as session:
            for number in range(4):
                user = User(email=f"user{number}@example.test", password_hash="unused")
                session.add(user)
                session.flush()
                ids.append(user.id)
                tokens.append(start_session(session, user))
            session.add_all([
                Friendship(requester_id=ids[1], addressee_id=ids[0], status="accepted"),
                Friendship(requester_id=ids[0], addressee_id=ids[2], status="pending"),
                Friendship(requester_id=ids[3], addressee_id=ids[0], status="blocked"),
            ])
        yield factory, tokens, ids
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


def client(token):
    return ASGIWebSocketSession(
        headers={"origin": ALLOWED_ORIGIN}, cookies={SESSION_COOKIE_NAME: token},
    )


@pytest.mark.parametrize("state", ["unknown", "stored_hash", "expired", "revoked", "deleted_user"])
async def test_postgres_invalid_cookie_rejected_before_registration(postgres_sessions, state):
    factory, tokens, ids = postgres_sessions
    token = tokens[0]
    with factory.begin() as session:
        stored = session.query(UserSession).filter_by(user_id=ids[0]).one()
        if state == "unknown":
            token = "unknown"
        elif state == "stored_hash":
            token = stored.token_hash
        elif state == "expired":
            stored.expires_at = func.now() - datetime.timedelta(seconds=1)
        elif state == "revoked":
            end_session(session, token)
        else:
            session.get(User, ids[0]).deleted_at = func.now()
    async with app.router.lifespan_context(app):
        await client(token).assert_rejected()
        assert manager.active_connections == {}
        assert manager.presence_queue.empty()


async def test_postgres_cookie_snapshot_friend_visibility_and_reconnect(postgres_sessions):
    _, tokens, ids = postgres_sessions
    sockets = [client(token) for token in tokens]
    async with app.router.lifespan_context(app):
        try:
            for index in (1, 2, 3):
                await sockets[index].connect()
                assert await sockets[index].receive_json() == {
                    "type": "presence_snapshot", "data": {"online_user_ids": []},
                }
            await sockets[0].connect()
            assert await sockets[0].receive_json() == {
                "type": "presence_snapshot", "data": {"online_user_ids": [ids[1]]},
            }
            assert await sockets[1].receive_json() == {
                "type": "presence", "data": {"user_id": ids[0], "online": True},
            }
            await sockets[0].disconnect()
            await asyncio.wait_for(manager.presence_queue.join(), 2)
            assert await sockets[1].receive_json() == {
                "type": "presence", "data": {"user_id": ids[0], "online": False},
            }
            sockets[0] = client(tokens[0])
            await sockets[0].connect()
            assert await sockets[0].receive_json() == {
                "type": "presence_snapshot", "data": {"online_user_ids": [ids[1]]},
            }
            assert await sockets[1].receive_json() == {
                "type": "presence", "data": {"user_id": ids[0], "online": True},
            }
            await asyncio.wait_for(manager.presence_queue.join(), 2)
            for index in (2, 3):
                assert sockets[index]._outgoing.empty()
        finally:
            for socket in sockets:
                if socket._task is not None:
                    await socket.disconnect()
            await asyncio.wait_for(manager.presence_queue.join(), 2)
        assert manager.active_connections == {}
