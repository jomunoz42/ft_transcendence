"""Tests for the session lifecycle: start, look up, end (auth issue #12)."""

import datetime

import pytest
from sqlalchemy import func, select, text, update

from app.auth.registration import register_user
from app.auth.sessions import end_session, start_session, user_for_token
from app.db.models import UserSession


def test_a_token_from_start_session_resolves_to_its_user(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")

    token = start_session(session, alice)

    assert user_for_token(session, token) == alice


def test_the_database_stores_only_the_hash_of_the_token(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")

    token = start_session(session, alice)

    stored = session.scalars(select(UserSession).where(UserSession.user_id == alice.id)).one()
    session.refresh(stored)
    assert token not in {str(value) for value in vars(stored).values()}
    assert len(stored.token_hash) == 64


def test_an_unknown_token_resolves_to_nobody(session):
    assert user_for_token(session, "not-a-real-token") is None


def test_an_expired_token_resolves_to_nobody(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    token = start_session(session, alice)
    stored = session.scalars(select(UserSession).where(UserSession.user_id == alice.id)).one()
    stored.expires_at = func.now() - datetime.timedelta(seconds=1)
    session.flush()

    assert user_for_token(session, token) is None


def test_after_end_session_the_token_resolves_to_nobody(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    token = start_session(session, alice)

    end_session(session, token)

    assert user_for_token(session, token) is None


def test_ending_an_unknown_or_already_ended_token_does_nothing(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    token = start_session(session, alice)
    other = start_session(session, alice)
    end_session(session, token)

    end_session(session, token)
    end_session(session, "not-a-real-token")

    assert user_for_token(session, other) == alice


def test_a_token_of_a_soft_deleted_user_resolves_to_nobody(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    token = start_session(session, alice)

    alice.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    session.flush()

    assert user_for_token(session, token) is None


def test_two_logins_are_independent_and_ending_one_keeps_the_other(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    laptop = start_session(session, alice)
    phone = start_session(session, alice)

    end_session(session, laptop)

    assert laptop != phone
    assert user_for_token(session, laptop) is None
    assert user_for_token(session, phone) == alice


def test_a_new_session_lasts_exactly_168_hours_even_across_a_clock_change(session):
    # A made-up zone whose clocks jump forward three days from today, so the week always crosses it.
    jump_day = (datetime.date.today().timetuple().tm_yday + 2) % 365
    session.execute(text(f"SET LOCAL TIME ZONE 'AAA0BBB,{jump_day}/0,{(jump_day + 180) % 365}/0'"))
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    start_session(session, alice)

    stored = session.scalars(select(UserSession).where(UserSession.user_id == alice.id)).one()
    session.refresh(stored)

    assert stored.expires_at - stored.created_at == datetime.timedelta(hours=168)


@pytest.mark.parametrize("token", [None, ""])
def test_a_missing_cookie_resolves_to_nobody(session, token):
    assert user_for_token(session, token) is None



def test_logging_in_deletes_the_users_expired_sessions_and_keeps_live_ones(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    start_session(session, alice)
    session.execute(
        update(UserSession)
        .where(UserSession.user_id == alice.id)
        .values(expires_at=func.now() - datetime.timedelta(seconds=1))
    )
    live = start_session(session, alice)

    start_session(session, alice)

    rows = session.scalar(select(func.count()).select_from(UserSession).where(UserSession.user_id == alice.id))
    assert rows == 2
    assert user_for_token(session, live) == alice
