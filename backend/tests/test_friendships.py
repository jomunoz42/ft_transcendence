"""Ticket 05: friendships, verified against real Postgres."""

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.db.models import Friendship, User


def make_user(session, email):
    user = User(email=email, password_hash="hash")
    session.add(user)
    session.flush()
    return user


def test_a_friend_request_starts_pending_and_can_be_accepted(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    request = Friendship(requester_id=alice.id, addressee_id=bob.id)
    session.add(request)
    session.flush()

    assert request.status == "pending"

    request.status = "accepted"
    session.flush()
    session.expire_all()

    stored = session.get(Friendship, request.id)
    assert stored.status == "accepted"
    assert (stored.requester.email, stored.addressee.email) == ("alice@myplaylist.test", "bob@myplaylist.test")


def test_a_user_cannot_befriend_themself(session):
    alice = make_user(session, "alice@myplaylist.test")

    session.add(Friendship(requester_id=alice.id, addressee_id=alice.id))

    with pytest.raises(IntegrityError):
        session.flush()


def test_a_pair_of_users_has_only_one_friendship_whoever_asked_first(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    session.add(Friendship(requester_id=alice.id, addressee_id=bob.id))
    session.flush()

    session.add(Friendship(requester_id=bob.id, addressee_id=alice.id))

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("leaver", ["requester", "addressee"])
def test_deleting_a_user_deletes_their_friendships(session, leaver):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    friendship = Friendship(requester_id=alice.id, addressee_id=bob.id, status="accepted")
    session.add(friendship)
    session.flush()
    gone = alice if leaver == "requester" else bob
    friendship_id = friendship.id

    # Direct statement, not session.delete(), so the database's ON DELETE CASCADE
    # does the work rather than SQLAlchemy's in-Python cascade.
    session.execute(delete(User).where(User.id == gone.id))
    session.expire_all()

    assert session.get(Friendship, friendship_id) is None


def test_a_status_outside_the_allowed_values_is_rejected(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")

    session.add(Friendship(requester_id=alice.id, addressee_id=bob.id, status="acepted"))

    with pytest.raises(IntegrityError):
        session.flush()
