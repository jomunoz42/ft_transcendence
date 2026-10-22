"""Blocks table: who blocked whom, verified against real Postgres."""

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.db.models import Block, User


def make_user(session, email):
    user = User(email=email, password_hash="hash")
    session.add(user)
    session.flush()
    return user


def test_a_block_is_stored_and_read_back(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")

    session.add(Block(blocker_id=alice.id, blocked_id=bob.id))
    session.flush()
    session.expire_all()

    stored = session.get(Block, (alice.id, bob.id))
    assert stored is not None
    assert stored.created_at is not None


def test_the_blocked_user_can_block_back(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")

    session.add_all([Block(blocker_id=alice.id, blocked_id=bob.id), Block(blocker_id=bob.id, blocked_id=alice.id)])
    session.flush()

    assert session.get(Block, (alice.id, bob.id)) is not None
    assert session.get(Block, (bob.id, alice.id)) is not None


def test_blocking_the_same_user_twice_is_rejected(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    session.add(Block(blocker_id=alice.id, blocked_id=bob.id))
    session.flush()
    session.expunge_all()

    session.add(Block(blocker_id=alice.id, blocked_id=bob.id))

    with pytest.raises(IntegrityError):
        session.flush()


def test_a_user_cannot_block_themself(session):
    alice = make_user(session, "alice@myplaylist.test")

    session.add(Block(blocker_id=alice.id, blocked_id=alice.id))

    with pytest.raises(IntegrityError):
        session.flush()


def test_blocking_a_user_who_does_not_exist_is_rejected(session):
    alice = make_user(session, "alice@myplaylist.test")

    session.add(Block(blocker_id=alice.id, blocked_id=alice.id + 1000))

    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_a_user_deletes_their_blocks(session):
    alice = make_user(session, "alice@myplaylist.test")
    bob = make_user(session, "bob@myplaylist.test")
    carol = make_user(session, "carol@myplaylist.test")
    session.add_all([Block(blocker_id=alice.id, blocked_id=bob.id), Block(blocker_id=carol.id, blocked_id=alice.id)])
    session.flush()

    session.execute(delete(User).where(User.id == alice.id))
    session.expire_all()

    assert session.get(Block, (alice.id, bob.id)) is None
    assert session.get(Block, (carol.id, alice.id)) is None
