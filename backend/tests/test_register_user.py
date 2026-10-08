"""Tests for registering a user (auth issue #11).

They call register_user the way the register route will, against real Postgres.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.auth.passwords import verify_password
from app.auth.registration import EmailTaken, InvalidRegistration, register_user
from app.db.models import Profile, User


def test_registering_creates_the_user_and_profile_with_a_verifiable_hash(session):
    user = register_user(session, "andre@myplaylist.test", "hunter22", "André")

    assert user.id is not None
    assert user.profile.display_name == "André"
    assert verify_password("hunter22", user.password_hash) is True


def test_the_stored_email_is_lowercased_and_stripped(session):
    user = register_user(session, "  Andre@MyPlaylist.TEST ", "hunter22", "André")

    assert user.email == "andre@myplaylist.test"


def test_an_email_already_registered_in_another_case_is_taken(session):
    register_user(session, "a@x.com", "hunter22", "First")

    with pytest.raises(EmailTaken):
        register_user(session, "A@x.com", "hunter22", "Second")


def test_a_taken_email_does_not_break_the_callers_transaction(session):
    first = register_user(session, "a@x.com", "hunter22", "First")
    with pytest.raises(EmailTaken):
        register_user(session, "a@x.com", "hunter22", "Second")

    other = register_user(session, "b@x.com", "hunter22", "Other")

    assert session.get(User, first.id) is not None
    assert other.id is not None


@pytest.mark.parametrize(
    "email",
    ["", "no-at-sign.com", "@x.com", "a@@x.com", "a@b@x.com", "a@x", "a@x.", "a@.com", "a b@x.com"],
)
def test_a_malformed_email_is_rejected(session, email):
    with pytest.raises(InvalidRegistration):
        register_user(session, email, "hunter22", "André")


@pytest.mark.parametrize("password", ["a" * 7, "a" * 129])
def test_a_password_outside_8_to_128_characters_is_rejected(session, password):
    with pytest.raises(InvalidRegistration):
        register_user(session, "a@x.com", password, "André")


@pytest.mark.parametrize("password", ["a" * 8, "a" * 128])
def test_a_password_of_exactly_8_or_128_characters_is_accepted(session, password):
    assert register_user(session, "a@x.com", password, "André").id is not None


def test_spaces_around_a_password_are_kept(session):
    user = register_user(session, "a@x.com", " hunter22 ", "André")

    assert verify_password(" hunter22 ", user.password_hash) is True
    assert verify_password("hunter22", user.password_hash) is False


@pytest.mark.parametrize("display_name", ["", "   ", "\t\n"])
def test_a_blank_display_name_is_rejected(session, display_name):
    with pytest.raises(InvalidRegistration):
        register_user(session, "a@x.com", "hunter22", display_name)


def test_the_display_name_is_stored_stripped(session):
    user = register_user(session, "a@x.com", "hunter22", "  André  ")

    assert user.profile.display_name == "André"


def rows(session):
    return tuple(session.scalar(select(func.count()).select_from(m)) for m in (User, Profile))


def test_a_rejected_registration_leaves_no_user_or_profile_behind(session):
    register_user(session, "a@x.com", "hunter22", "First")
    before = rows(session)

    with pytest.raises(EmailTaken):
        register_user(session, "a@x.com", "hunter22", "Second")
    with pytest.raises(InvalidRegistration):
        register_user(session, "b@x.com", "short", "Third")

    assert rows(session) == before


def test_a_broken_change_the_caller_left_pending_is_not_reported_as_email_taken(session):
    session.add(Profile(user_id=-1, display_name="Orphan"))  # no such user: foreign key fails

    with pytest.raises(IntegrityError):
        register_user(session, "a@x.com", "hunter22", "André")


@pytest.mark.parametrize(
    ("email", "display_name"),
    [("a\x00b@x.com", "André"), ("a@x.com", "An\x00dré")],
)
def test_a_nul_character_is_rejected_before_reaching_the_database(session, email, display_name):
    with pytest.raises(InvalidRegistration):
        register_user(session, email, "hunter22", display_name)
