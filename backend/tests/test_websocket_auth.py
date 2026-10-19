"""Exercise the WebSocket auth helper without a running PostgreSQL server.

The SQLite fixture uses the real user/session models and token lookup. It seeds
explicit IDs and timestamps because PostgreSQL's BIGINT autoincrement and the
interval arithmetic in start_session are not portable to SQLite. PostgreSQL
constraints and session creation remain covered by the existing session tests.
"""

import datetime
import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

import app.auth.websocket as websocket_auth
from app.auth.sessions import end_session
from app.db.models import Base, User, UserSession


@pytest.mark.parametrize("token", [None, ""])
def test_missing_token_does_not_open_a_session_or_look_up_a_user(monkeypatch, token):
    factory = Mock(side_effect=AssertionError("unexpected database access"))
    lookup = Mock(side_effect=AssertionError("unexpected token lookup"))
    monkeypatch.setattr(websocket_auth, "SessionLocal", factory)
    monkeypatch.setattr(websocket_auth, "user_for_token", lookup)

    assert websocket_auth.authenticate_websocket(token) is None

    factory.assert_not_called()
    lookup.assert_not_called()


@pytest.mark.parametrize("user, expected", [(SimpleNamespace(id=42), 42), (None, None)])
def test_helper_returns_user_id_and_releases_the_database_session(monkeypatch, user, expected):
    context = MagicMock()
    factory = Mock(return_value=context)
    lookup = Mock(return_value=user)
    monkeypatch.setattr(websocket_auth, "SessionLocal", factory)
    monkeypatch.setattr(websocket_auth, "user_for_token", lookup)

    assert websocket_auth.authenticate_websocket("raw-token") == expected

    factory.assert_called_once_with()
    context.__enter__.assert_called_once_with()
    lookup.assert_called_once_with(context.__enter__.return_value, "raw-token")
    context.__exit__.assert_called_once_with(None, None, None)


def test_lookup_error_propagates_but_releases_the_database_session(monkeypatch):
    context = MagicMock()
    context.__exit__.return_value = False
    error = SQLAlchemyError("database unavailable")
    monkeypatch.setattr(websocket_auth, "SessionLocal", Mock(return_value=context))
    monkeypatch.setattr(websocket_auth, "user_for_token", Mock(side_effect=error))

    with pytest.raises(SQLAlchemyError, match="database unavailable"):
        websocket_auth.authenticate_websocket("raw-token")

    context.__exit__.assert_called_once()
    assert context.__exit__.call_args.args[:2] == (SQLAlchemyError, error)


@pytest.fixture
def token_database(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    factory = sessionmaker(bind=engine)
    token = "raw-websocket-session-token"
    try:
        Base.metadata.create_all(engine, tables=[User.__table__, UserSession.__table__])
        with factory.begin() as session:
            session.add(User(id=42, email="alice@example.test", password_hash="unused"))
            session.flush()
            now = session.scalar(select(func.now()))
            session.add(UserSession(
                id=1,
                user_id=42,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=now + datetime.timedelta(days=7),
            ))
        monkeypatch.setattr(websocket_auth, "SessionLocal", factory)
        yield factory, token
    finally:
        engine.dispose()


def test_live_token_resolves_to_user_id_using_the_real_lookup(token_database):
    _, token = token_database

    assert websocket_auth.authenticate_websocket(token) == 42


@pytest.mark.parametrize("state", ["unknown", "stored_hash", "expired", "revoked", "deleted_user"])
def test_invalid_sessions_resolve_to_nobody_using_the_real_lookup(token_database, state):
    factory, token = token_database
    # Establish validity first so the rejection cannot pass due to broken setup.
    assert websocket_auth.authenticate_websocket(token) == 42

    with factory.begin() as session:
        if state == "unknown":
            token = "not-a-real-token"
        elif state == "stored_hash":
            token = session.scalars(select(UserSession)).one().token_hash
        elif state == "expired":
            stored = session.scalars(select(UserSession).where(UserSession.user_id == 42)).one()
            # Same lifecycle pattern as test_session_lifecycle, with the database
            # time read before doing interval arithmetic for SQLite compatibility.
            stored.expires_at = session.scalar(select(func.now())) - datetime.timedelta(seconds=1)
            session.flush()
        elif state == "revoked":
            end_session(session, token)
        elif state == "deleted_user":
            session.get(User, 42).deleted_at = func.now()
            session.flush()

    assert websocket_auth.authenticate_websocket(token) is None
