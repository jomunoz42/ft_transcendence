"""Auth ticket 02: the sessions table, verified against real Postgres."""

import datetime

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.db.models import User, UserSession


def make_user(session, email):
    user = User(email=email, password_hash="hash")
    session.add(user)
    session.flush()
    return user


def in_7_days():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)


def test_a_session_is_stored_and_read_back_with_its_user(session):
    alice = make_user(session, "alice@myplaylist.test")
    login = UserSession(user_id=alice.id, token_hash="a" * 64, expires_at=in_7_days())
    session.add(login)
    session.flush()
    session.expire_all()

    stored = session.get(UserSession, login.id)
    assert stored.token_hash == "a" * 64
    assert stored.user.email == "alice@myplaylist.test"
    assert stored.created_at is not None


def test_two_sessions_with_the_same_token_hash_are_rejected(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    session.add(UserSession(user_id=alice.id, token_hash="a" * 64, expires_at=in_7_days()))
    session.flush()

    session.add(UserSession(user_id=bob.id, token_hash="a" * 64, expires_at=in_7_days()))

    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_a_user_deletes_their_sessions(session):
    alice = make_user(session, "alice@myplaylist.test")
    login = UserSession(user_id=alice.id, token_hash="a" * 64, expires_at=in_7_days())
    session.add(login)
    session.flush()
    login_id = login.id

    # Direct statement, not session.delete(), so the database's ON DELETE CASCADE
    # does the work rather than SQLAlchemy's in-Python cascade.
    session.execute(delete(User).where(User.id == alice.id))
    session.expire_all()

    assert session.get(UserSession, login_id) is None
