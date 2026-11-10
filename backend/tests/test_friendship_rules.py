"""Friendship rules: who may send, answer, remove and block, verified against real Postgres."""

import datetime

import pytest
from sqlalchemy import func, insert, select

from app.db.models import Block, Friendship, User
from app.routes.v1.friendships import (
    NotAllowed, NotFound, accept_request, block_user, cancel_request, check_not_blocked, decline_request,
    remove_friend, send_request, unblock_user,
)


def make_user(session, email):
    user = User(email=email, password_hash="hash")
    session.add(user)
    session.flush()
    return user


def block(session, blocker, blocked):
    session.add(Block(blocker_id=blocker.id, blocked_id=blocked.id))
    session.flush()


# check_not_blocked

def test_no_block_between_two_users_lets_the_action_through(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")

    check_not_blocked(session, alice.id, bob.id)


def test_a_blocked_user_acting_on_the_blocker_sees_not_found(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    block(session, alice, bob)

    with pytest.raises(NotFound):
        check_not_blocked(session, bob.id, alice.id)


def test_the_blocker_acting_on_the_blocked_user_is_told_to_unblock_first(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    block(session, alice, bob)

    with pytest.raises(NotAllowed):
        check_not_blocked(session, alice.id, bob.id)


def request(session, requester, addressee, status="pending"):
    row = Friendship(requester_id=requester.id, addressee_id=addressee.id, status=status)
    session.add(row)
    session.flush()
    return row


# accept_request

def test_accepting_a_request_sent_to_me_makes_us_friends(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    row = request(session, bob, alice)

    accepted = accept_request(session, alice.id, bob.id)

    assert (accepted.id, accepted.status) == (row.id, "accepted")


def test_i_cannot_accept_my_own_request(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    row = request(session, alice, bob)

    with pytest.raises(NotFound):
        accept_request(session, alice.id, bob.id)
    assert row.status == "pending"


@pytest.mark.parametrize("status", [None, "accepted", "declined"])
def test_there_is_nothing_to_accept_without_a_pending_request(session, status):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    if status is not None:
        request(session, bob, alice, status)

    with pytest.raises(NotFound):
        accept_request(session, alice.id, bob.id)


def test_a_blocked_user_cannot_accept_and_is_not_told_why(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    row = request(session, alice, bob)
    block(session, alice, bob)

    with pytest.raises(NotFound):
        accept_request(session, bob.id, alice.id)
    assert row.status == "pending"


# decline_request

def test_declining_a_request_sent_to_me_keeps_the_row_as_declined(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    row = request(session, bob, alice)

    decline_request(session, alice.id, bob.id)

    assert row.status == "declined"
    assert (row.requester_id, row.addressee_id) == (bob.id, alice.id)


def test_i_cannot_decline_my_own_request(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    row = request(session, alice, bob)

    with pytest.raises(NotFound):
        decline_request(session, alice.id, bob.id)
    assert row.status == "pending"


@pytest.mark.parametrize("status", [None, "accepted", "declined"])
def test_there_is_nothing_to_decline_without_a_pending_request(session, status):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    if status is not None:
        request(session, bob, alice, status)

    with pytest.raises(NotFound):
        decline_request(session, alice.id, bob.id)


def test_a_blocked_user_cannot_decline_and_is_not_told_why(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    row = request(session, alice, bob)
    block(session, alice, bob)

    with pytest.raises(NotFound):
        decline_request(session, bob.id, alice.id)
    assert row.status == "pending"


# cancel_request

def friendship_rows(session):
    return session.scalar(select(func.count()).select_from(Friendship))


def test_cancelling_my_request_deletes_it_and_either_of_us_can_ask_again(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    request(session, alice, bob)

    cancel_request(session, alice.id, bob.id)

    assert friendship_rows(session) == 0
    assert send_request(session, bob.id, alice.id).status == "pending"


def test_i_cannot_cancel_a_request_sent_to_me(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    row = request(session, bob, alice)

    with pytest.raises(NotFound):
        cancel_request(session, alice.id, bob.id)
    assert row.status == "pending"


@pytest.mark.parametrize("status", [None, "accepted", "declined"])
def test_there_is_nothing_to_cancel_without_my_pending_request(session, status):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    if status is not None:
        request(session, alice, bob, status)

    with pytest.raises(NotFound):
        cancel_request(session, alice.id, bob.id)


def test_a_blocked_user_cannot_cancel_and_is_not_told_why(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    request(session, bob, alice)
    block(session, alice, bob)

    with pytest.raises(NotFound):
        cancel_request(session, bob.id, alice.id)
    assert friendship_rows(session) == 1


# remove_friend

@pytest.mark.parametrize("remover", ["requester", "addressee"])
def test_either_friend_can_remove_and_then_either_can_ask_again(session, remover):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    request(session, alice, bob, "accepted")
    me, them = (alice, bob) if remover == "requester" else (bob, alice)

    remove_friend(session, me.id, them.id)

    assert friendship_rows(session) == 0
    assert send_request(session, them.id, me.id).status == "pending"


@pytest.mark.parametrize("status", [None, "pending", "declined"])
def test_there_is_nothing_to_remove_without_a_friendship(session, status):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    if status is not None:
        request(session, bob, alice, status)

    with pytest.raises(NotFound):
        remove_friend(session, alice.id, bob.id)
    assert friendship_rows(session) == (0 if status is None else 1)


def test_a_blocked_user_cannot_remove_and_is_not_told_why(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    request(session, alice, bob, "accepted")
    block(session, alice, bob)

    with pytest.raises(NotFound):
        remove_friend(session, bob.id, alice.id)
    assert friendship_rows(session) == 1


# block_user

def block_rows(session):
    return session.scalar(select(func.count()).select_from(Block))


def test_blocking_a_stranger_stores_the_block(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")

    block_user(session, alice.id, bob.id)

    assert session.get(Block, (alice.id, bob.id)) is not None


@pytest.mark.parametrize("status", ["accepted", "pending", "declined"])
def test_blocking_deletes_the_pair_friendship_row(session, status):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    request(session, bob, alice, status)

    block_user(session, alice.id, bob.id)

    assert friendship_rows(session) == 0
    assert session.get(Block, (alice.id, bob.id)) is not None


def test_blocking_twice_changes_nothing(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    block_user(session, alice.id, bob.id)

    block_user(session, alice.id, bob.id)

    assert block_rows(session) == 1


def test_a_block_written_between_the_check_and_the_insert_changes_nothing(session, monkeypatch):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    session.execute(insert(Block).values(blocker_id=alice.id, blocked_id=bob.id))
    real_get = session.get
    missed = []

    def get_missing_the_first_block(model, key, **kw):
        if model is Block and not missed:
            missed.append(key)
            return None
        return real_get(model, key, **kw)

    monkeypatch.setattr(session, "get", get_missing_the_first_block)

    block_user(session, alice.id, bob.id)

    assert block_rows(session) == 1


def test_the_blocked_user_can_block_back(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    block_user(session, alice.id, bob.id)

    block_user(session, bob.id, alice.id)

    assert block_rows(session) == 2


@pytest.mark.parametrize("target", ["unknown", "deleted"])
def test_blocking_a_user_who_does_not_exist_is_not_found(session, target):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    bob.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    session.flush()
    them_id = alice.id + 1000 if target == "unknown" else bob.id

    with pytest.raises(NotFound):
        block_user(session, alice.id, them_id)
    assert block_rows(session) == 0


def test_i_cannot_block_myself(session):
    alice = make_user(session, "alice@myplaylist.test")

    with pytest.raises(NotAllowed):
        block_user(session, alice.id, alice.id)
    assert block_rows(session) == 0


# unblock_user

def test_unblocking_lifts_my_block_and_we_are_strangers_again(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    request(session, alice, bob, "accepted")
    block_user(session, alice.id, bob.id)

    unblock_user(session, alice.id, bob.id)

    assert block_rows(session) == 0
    assert friendship_rows(session) == 0
    assert send_request(session, bob.id, alice.id).status == "pending"


def test_there_is_nothing_to_unblock_without_my_block(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")

    with pytest.raises(NotFound):
        unblock_user(session, alice.id, bob.id)


def test_only_the_blocker_can_lift_a_block(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    block_user(session, alice.id, bob.id)

    with pytest.raises(NotFound):
        unblock_user(session, bob.id, alice.id)
    assert block_rows(session) == 1


def test_unblocking_leaves_the_other_users_block_in_place(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    block_user(session, alice.id, bob.id)
    block_user(session, bob.id, alice.id)

    unblock_user(session, alice.id, bob.id)

    assert session.get(Block, (bob.id, alice.id)) is not None
    with pytest.raises(NotFound):
        send_request(session, alice.id, bob.id)


# deleted accounts

def asked(requester, addressee, status="pending"):
    return lambda session: session.add(Friendship(requester_id=requester.id, addressee_id=addressee.id, status=status))


DELETED_BOB_CASES = {
    "send": (send_request, lambda alice, bob: None),
    "accept": (accept_request, lambda alice, bob: asked(bob, alice)),
    "decline": (decline_request, lambda alice, bob: asked(bob, alice)),
    "cancel": (cancel_request, lambda alice, bob: asked(alice, bob)),
    "remove": (remove_friend, lambda alice, bob: asked(alice, bob, "accepted")),
    "unblock": (unblock_user, lambda alice, bob: lambda session: session.add(Block(blocker_id=alice.id, blocked_id=bob.id))),
}


@pytest.mark.parametrize("action", DELETED_BOB_CASES)
def test_every_action_on_a_deleted_account_is_not_found_and_changes_nothing(session, action):
    rule, existing_row = DELETED_BOB_CASES[action]
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    add_row = existing_row(alice, bob)
    if add_row:
        add_row(session)
    bob.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    session.flush()
    before = (friendship_rows(session), block_rows(session), session.scalar(select(Friendship.status)))

    with pytest.raises(NotFound):
        rule(session, alice.id, bob.id)
    assert (friendship_rows(session), block_rows(session), session.scalar(select(Friendship.status))) == before
