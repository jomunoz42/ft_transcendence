"""are_friends and list_friends: who counts as a friend, from either side of the pair."""

import datetime

import pytest

from app.db.friendships import are_friends, list_friends, send_friend_request
from app.db.models import Friendship, User


def make_user(session, email):
    user = User(email=email, password_hash="hash")
    session.add(user)
    session.flush()
    return user


def befriend(session, a, b):
    send_friend_request(session, a.id, b.id)
    send_friend_request(session, b.id, a.id)


def pair_with_status(session, requester, addressee, status):
    session.add(Friendship(requester_id=requester.id, addressee_id=addressee.id, status=status))
    session.flush()


def ids(users):
    return [user.id for user in users]


# are_friends

def test_an_accepted_pair_are_friends_whichever_way_you_ask(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    befriend(session, alice, bob)

    assert are_friends(session, alice.id, bob.id) is True
    assert are_friends(session, bob.id, alice.id) is True


def test_users_who_never_interacted_are_not_friends(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")

    assert are_friends(session, alice.id, bob.id) is False


@pytest.mark.parametrize("status", ["pending", "declined", "blocked"])
def test_a_pair_that_is_not_accepted_are_not_friends(session, status):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    pair_with_status(session, alice, bob, status)

    assert are_friends(session, alice.id, bob.id) is False
    assert are_friends(session, bob.id, alice.id) is False


# list_friends

def test_friends_come_from_both_sides_ordered_by_user_id(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    carol = make_user(session, "carol@myplaylist.test")
    befriend(session, carol, alice)  # Carol asked Alice
    befriend(session, alice, bob)  # Alice asked Bob

    assert ids(list_friends(session, alice.id)) == [bob.id, carol.id]


def test_someone_with_no_friends_gets_an_empty_list(session):
    alice = make_user(session, "alice@myplaylist.test")

    assert list_friends(session, alice.id) == []


def test_pending_declined_and_blocked_pairs_are_left_out(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    carol = make_user(session, "carol@myplaylist.test")
    dave = make_user(session, "dave@myplaylist.test")
    erin = make_user(session, "erin@myplaylist.test")
    befriend(session, alice, bob)
    pair_with_status(session, alice, carol, "pending")
    pair_with_status(session, dave, alice, "declined")
    pair_with_status(session, alice, erin, "blocked")

    assert ids(list_friends(session, alice.id)) == [bob.id]


def test_a_soft_deleted_friend_is_left_out(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    carol = make_user(session, "carol@myplaylist.test")
    befriend(session, alice, bob)
    befriend(session, alice, carol)
    carol.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    session.flush()

    assert ids(list_friends(session, alice.id)) == [bob.id]
