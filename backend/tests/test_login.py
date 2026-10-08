"""Tests for logging in with lockout (auth issue #13)."""

import datetime

import pytest
from sqlalchemy import func, select

from app.auth.login import InvalidCredentials, authenticate
from app.auth.registration import register_user


def test_the_right_email_and_password_return_the_user_whatever_the_email_case(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")

    assert authenticate(session, "  Alice@X.COM ", "hunter22") == alice


def test_a_wrong_password_is_refused_and_counted(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")

    with pytest.raises(InvalidCredentials):
        authenticate(session, "alice@x.com", "wrong-password")

    session.refresh(alice)
    assert alice.failed_login_count == 1


def test_an_unknown_email_gets_the_same_error(session):
    with pytest.raises(InvalidCredentials):
        authenticate(session, "nobody@x.com", "hunter22")


def fail(session, email, times):
    """Try a wrong password this many times."""
    for _ in range(times):
        with pytest.raises(InvalidCredentials):
            authenticate(session, email, "wrong-password")


def test_four_wrong_attempts_do_not_lock_the_account(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")

    fail(session, "alice@x.com", 4)

    session.refresh(alice)
    assert alice.locked_until is None
    assert authenticate(session, "alice@x.com", "hunter22") == alice


def test_the_fifth_wrong_attempt_locks_the_account_for_15_minutes(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")

    fail(session, "alice@x.com", 5)

    session.refresh(alice)
    lock = alice.locked_until - session.scalar(select(func.now()))
    assert datetime.timedelta(minutes=14) < lock <= datetime.timedelta(minutes=15)
    assert alice.failed_login_count == 0


def test_a_locked_account_is_refused_even_with_the_right_password(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    fail(session, "alice@x.com", 5)
    locked_until = alice.locked_until

    with pytest.raises(InvalidCredentials):
        authenticate(session, "alice@x.com", "hunter22")
    fail(session, "alice@x.com", 3)

    session.refresh(alice)
    assert alice.locked_until == locked_until
    assert alice.failed_login_count == 0


def test_once_the_lock_has_expired_the_right_password_works_again(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    fail(session, "alice@x.com", 5)
    alice.locked_until = func.now() - datetime.timedelta(seconds=1)
    session.flush()

    assert authenticate(session, "alice@x.com", "hunter22") == alice
    session.refresh(alice)
    assert alice.locked_until is None


def test_a_successful_login_resets_the_failed_attempt_count(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    fail(session, "alice@x.com", 3)

    authenticate(session, "alice@x.com", "hunter22")

    session.refresh(alice)
    assert alice.failed_login_count == 0


def test_a_soft_deleted_user_is_refused(session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    alice.deleted_at = func.now()
    session.flush()

    with pytest.raises(InvalidCredentials):
        authenticate(session, "alice@x.com", "hunter22")
