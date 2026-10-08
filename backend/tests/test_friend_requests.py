"""send_friend_request: the rules for asking someone to be your friend."""

import pytest
from sqlalchemy import func, select

from app.db.friendships import FriendRequestNotAllowed, send_friend_request
from app.db.models import Friendship, User


def make_user(session, email):
    user = User(email=email, password_hash="hash")
    session.add(user)
    session.flush()
    return user


def friendship_rows(session):
    return session.scalar(select(func.count()).select_from(Friendship))


def test_asking_a_stranger_creates_a_pending_request(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")

    request = send_friend_request(session, alice.id, bob.id)

    assert (request.requester_id, request.addressee_id, request.status) == (alice.id, bob.id, "pending")


def test_asking_someone_who_already_asked_you_makes_you_friends(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    send_friend_request(session, alice.id, bob.id)

    friendship = send_friend_request(session, bob.id, alice.id)

    assert friendship.status == "accepted"
    assert friendship_rows(session) == 1


def test_asking_twice_changes_nothing(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    first = send_friend_request(session, alice.id, bob.id)

    again = send_friend_request(session, alice.id, bob.id)

    assert again.id == first.id
    assert again.status == "pending"
    assert friendship_rows(session) == 1


def test_asking_an_existing_friend_changes_nothing(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    send_friend_request(session, alice.id, bob.id)
    friendship = send_friend_request(session, bob.id, alice.id)

    for requester, addressee in [(alice, bob), (bob, alice)]:
        again = send_friend_request(session, requester.id, addressee.id)
        assert (again.id, again.status) == (friendship.id, "accepted")


def test_someone_who_was_declined_cannot_ask_again(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    request = send_friend_request(session, alice.id, bob.id)
    request.status = "declined"  # Bob said no
    session.flush()

    with pytest.raises(FriendRequestNotAllowed):
        send_friend_request(session, alice.id, bob.id)
    assert request.status == "declined"


def test_the_person_who_declined_can_ask_back(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    request = send_friend_request(session, alice.id, bob.id)
    request.status = "declined"  # Bob said no
    session.flush()

    reopened = send_friend_request(session, bob.id, alice.id)

    # Bob now waits for Alice; she is not made his friend without saying yes.
    assert (reopened.requester_id, reopened.addressee_id, reopened.status) == (bob.id, alice.id, "pending")
    assert friendship_rows(session) == 1


@pytest.mark.parametrize("asker", ["requester", "addressee"])
def test_nobody_can_ask_across_a_block(session, asker):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    friendship = send_friend_request(session, alice.id, bob.id)
    friendship.status = "blocked"
    session.flush()
    requester, addressee = (alice, bob) if asker == "requester" else (bob, alice)

    with pytest.raises(FriendRequestNotAllowed):
        send_friend_request(session, requester.id, addressee.id)
    assert friendship.status == "blocked"


@pytest.mark.parametrize("addressee", ["self", "unknown"])
def test_an_impossible_request_is_refused_and_the_session_keeps_working(session, addressee):
    alice = make_user(session, "alice@myplaylist.test")
    addressee_id = alice.id if addressee == "self" else -1

    with pytest.raises(FriendRequestNotAllowed):
        send_friend_request(session, alice.id, addressee_id)

    bob = make_user(session, "bob@myplaylist.test")
    assert send_friend_request(session, alice.id, bob.id).status == "pending"
