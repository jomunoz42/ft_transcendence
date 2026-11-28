"""Logging in with a 42 account through login_with_42, against real Postgres."""

import datetime

import pytest
from fastapi import HTTPException

from app.auth.login import authenticate
from app.auth.oauth import login_with_42, new_state, state_matches
from app.auth.registration import register_user


def test_a_new_42_account_creates_a_user_with_a_profile_and_no_password(session):
    profile = {"id": 4242, "login": "alencart", "email": "alencart@student.42.fr"}

    user = login_with_42(session, profile)

    assert user.id is not None
    assert user.email == "alencart@student.42.fr"
    assert user.profile.display_name == "alencart"
    assert user.password_hash is None


def test_logging_in_again_with_the_same_42_account_returns_the_same_user(session):
    profile = {"id": 4242, "login": "alencart", "email": "alencart@student.42.fr"}

    first = login_with_42(session, profile)
    second = login_with_42(session, profile)

    assert second.id == first.id


def test_a_42_email_already_used_by_a_password_account_is_taken_and_not_linked(session):
    register_user(session, "alencart@student.42.fr", "hunter22", "André")
    profile = {"id": 4242, "login": "alencart", "email": "alencart@student.42.fr"}

    with pytest.raises(HTTPException) as exc:
        login_with_42(session, profile)
    assert exc.value.status_code == 409

    with pytest.raises(HTTPException) as again:
        login_with_42(session, profile)
    assert again.value.status_code == 409


def test_logging_in_with_the_42_account_of_a_deleted_user_is_refused(session):
    profile = {"id": 4242, "login": "alencart", "email": "alencart@student.42.fr"}
    user = login_with_42(session, profile)
    user.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    session.flush()

    with pytest.raises(HTTPException) as exc:
        login_with_42(session, profile)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("email", [None, ""])
def test_a_42_profile_without_an_email_is_refused(session, email):
    profile = {"id": 4242, "login": "alencart", "email": email}

    with pytest.raises(HTTPException) as exc:
        login_with_42(session, profile)
    assert exc.value.status_code == 422


def test_a_password_login_on_a_42_only_account_is_refused(session):
    login_with_42(session, {"id": 4242, "login": "alencart", "email": "alencart@student.42.fr"})

    with pytest.raises(HTTPException) as exc:
        authenticate(session, "alencart@student.42.fr", "any-password")
    assert exc.value.status_code == 401


def test_registering_with_the_email_of_a_42_account_is_taken(session):
    login_with_42(session, {"id": 4242, "login": "alencart", "email": "alencart@student.42.fr"})

    with pytest.raises(HTTPException) as exc:
        register_user(session, "alencart@student.42.fr", "hunter22", "André")
    assert exc.value.status_code == 409


def test_each_new_state_is_different():
    assert new_state() != new_state()


def test_the_state_from_the_cookie_matches_the_same_state_from_42():
    state = new_state()

    assert state_matches(state, state) is True


@pytest.mark.parametrize(
    "cookie, query",
    [("abc", "abd"), (None, "abc"), ("abc", None), (None, None), ("", ""), ("abc", "é"), ("é", "abc")],
)
def test_a_different_or_missing_state_does_not_match(cookie, query):
    assert state_matches(cookie, query) is False
