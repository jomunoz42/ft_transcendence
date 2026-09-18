"""Ticket 03: users and profiles, verified against real Postgres."""

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.db.models import Profile, User


def test_a_user_and_profile_can_be_stored_and_read_back(session):
    user = User(email="andre@myplaylist.test", password_hash="not-a-real-hash")
    user.profile = Profile(display_name="André", bio="The social side.")
    session.add(user)
    session.flush()

    stored = session.get(User, user.id)

    assert stored.email == "andre@myplaylist.test"
    assert stored.profile.display_name == "André"
    assert stored.profile.bio == "The social side."


def test_two_users_cannot_share_an_email(session):
    session.add(User(email="taken@myplaylist.test", password_hash="hash-one"))
    session.flush()

    session.add(User(email="taken@myplaylist.test", password_hash="hash-two"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_a_user_deletes_their_profile(session):
    user = User(email="leaving@myplaylist.test", password_hash="hash")
    user.profile = Profile(display_name="Leaving")
    session.add(user)
    session.flush()
    profile_id = user.profile.id

    # Deleted with a direct statement rather than session.delete(), so this
    # exercises the database's ON DELETE CASCADE instead of SQLAlchemy's
    # in-Python cascade. A user removed by anything other than the ORM must not
    # leave an orphaned profile behind.
    session.execute(delete(User).where(User.id == user.id))
    session.expire_all()

    assert session.get(Profile, profile_id) is None


def test_a_top10_is_private_by_default_and_can_be_made_public(session):
    """Privacy defaults closed: a new profile is visible to friends, not the world."""
    user = User(email="private@myplaylist.test", password_hash="hash")
    user.profile = Profile(display_name="Private")
    session.add(user)
    session.flush()

    assert user.profile.is_top10_public is False

    user.profile.is_top10_public = True
    session.flush()
    session.expire_all()

    assert session.get(User, user.id).profile.is_top10_public is True
