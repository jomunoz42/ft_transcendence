"""The messages table: what PostgreSQL itself enforces for private chat messages."""

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import DataError, IntegrityError

from app.db.models import Friendship, Message, User


def make_user(session, email):
    user = User(email=email, password_hash="hash")
    session.add(user)
    session.flush()
    return user


@pytest.fixture
def alice(session):
    return make_user(session, "alice@chat.test")


@pytest.fixture
def bob(session):
    return make_user(session, "bob@chat.test")


def send(session, sender, recipient, body="hi"):
    message = Message(sender_id=sender.id, recipient_id=recipient.id, body=body)
    session.add(message)
    session.flush()
    return message


def test_a_message_keeps_its_sender_recipient_body_and_time(session, alice, bob):
    message_id = send(session, alice, bob, "hello Bob").id
    session.expire_all()

    message = session.get(Message, message_id)
    assert (message.sender.email, message.recipient.email, message.body) == ("alice@chat.test", "bob@chat.test", "hello Bob")
    assert message.created_at is not None


CHECK_FAILED, TOO_LONG = "23514", "22001"


@pytest.mark.parametrize("body", ["x" * 1000, "é" * 1000, "🎵" * 1000])
def test_up_to_1000_characters_are_stored_whatever_their_size_in_bytes(session, alice, bob, body):
    assert send(session, alice, bob, body).body == body


@pytest.mark.parametrize(("body", "pgcode"), [
    ("", CHECK_FAILED), ("   ", CHECK_FAILED), ("\n\t ", CHECK_FAILED),
    ("x" * 1001, TOO_LONG), ("é" * 1001, TOO_LONG),
])
def test_an_empty_blank_or_too_long_message_is_refused(session, alice, bob, body, pgcode):
    with pytest.raises((IntegrityError, DataError)) as refused:
        send(session, alice, bob, body)
    assert refused.value.orig.pgcode == pgcode


def test_nobody_can_message_themselves(session, alice):
    with pytest.raises(IntegrityError) as refused:
        send(session, alice, alice)
    assert refused.value.orig.pgcode == CHECK_FAILED


def message_count(session, *users):
    ids = [user.id for user in users]
    return session.scalar(select(func.count()).select_from(Message).where(
        Message.sender_id.in_(ids), Message.recipient_id.in_(ids),
    ))


@pytest.mark.parametrize("via_orm", [False, True])
@pytest.mark.parametrize("who", ["alice", "bob"])
def test_deleting_either_account_deletes_their_conversation_and_nothing_else(session, alice, bob, who, via_orm):
    carol = make_user(session, "carol@chat.test")
    send(session, alice, bob, "to bob")
    send(session, bob, alice, "to alice")
    send(session, alice, carol, "to carol")

    deleted = {"alice": alice, "bob": bob}[who]
    if via_orm:
        session.delete(deleted)
        session.flush()
    else:
        session.execute(delete(User).where(User.id == deleted.id))

    assert message_count(session, alice, bob) == 0
    assert message_count(session, alice, carol) == (0 if who == "alice" else 1)


def test_ending_the_friendship_keeps_the_conversation(session, alice, bob):
    friendship = Friendship(requester_id=alice.id, addressee_id=bob.id, status="accepted")
    session.add(friendship)
    send(session, alice, bob, "to bob")
    send(session, bob, alice, "to alice")

    session.delete(friendship)
    session.flush()

    assert message_count(session, alice, bob) == 2
