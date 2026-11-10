"""crud.friendship queries that the friendship rules build on, verified against real Postgres."""

import datetime

import pytest

from app.crud.friendship import ErrorCreatingFriendship, create_friendship, is_blocked, list_pending
from app.db.models import Block, Friendship, User


def make_user(session, email):
    user = User(email=email, password_hash="hash")
    session.add(user)
    session.flush()
    return user


def test_is_blocked_sees_a_block_from_either_side(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    session.add(Block(blocker_id=alice.id, blocked_id=bob.id))
    session.flush()

    assert is_blocked(session, alice.id, bob.id) is True
    assert is_blocked(session, bob.id, alice.id) is True


def test_is_blocked_is_false_without_a_block(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    carol = make_user(session, "carol@myplaylist.test")
    session.add(Block(blocker_id=alice.id, blocked_id=carol.id))
    session.flush()

    assert is_blocked(session, alice.id, bob.id) is False


def ids(users):
    return [user.id for user in users]


def test_list_pending_splits_requests_to_me_from_requests_I_sent(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    carol = make_user(session, "carol@myplaylist.test")
    dave = make_user(session, "dave@myplaylist.test")
    session.add_all([
        Friendship(requester_id=bob.id, addressee_id=alice.id),
        Friendship(requester_id=dave.id, addressee_id=alice.id),
        Friendship(requester_id=alice.id, addressee_id=carol.id),
    ])
    session.flush()

    incoming, outgoing = list_pending(session, alice.id)

    assert ids(incoming) == [bob.id, dave.id]
    assert ids(outgoing) == [carol.id]


def test_list_pending_leaves_out_answered_requests_and_deleted_accounts(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    carol = make_user(session, "carol@myplaylist.test")
    erin = make_user(session, "erin@myplaylist.test")
    session.add_all([
        Friendship(requester_id=bob.id, addressee_id=alice.id, status="accepted"),
        Friendship(requester_id=alice.id, addressee_id=carol.id, status="declined"),
        Friendship(requester_id=erin.id, addressee_id=alice.id),
    ])
    erin.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    session.flush()

    assert list_pending(session, alice.id) == ([], [])


def test_create_friendship_inserts_a_pending_request(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")

    request = create_friendship(session, alice.id, bob.id)

    assert (request.requester_id, request.addressee_id, request.status) == (alice.id, bob.id, "pending")


def test_create_friendship_returns_none_when_the_pair_already_has_a_row(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    session.add(Friendship(requester_id=bob.id, addressee_id=alice.id))
    session.flush()

    assert create_friendship(session, alice.id, bob.id) is None


def test_create_friendship_refuses_asking_yourself(session):
    alice = make_user(session, "alice@myplaylist.test")

    with pytest.raises(ErrorCreatingFriendship):
        create_friendship(session, alice.id, alice.id)
