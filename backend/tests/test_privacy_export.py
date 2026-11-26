"""The export route is scoped to the logged-in user and has a small public schema."""

import json

import pytest

from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.sessions import start_session
from app.db.models import (
    Block, Friendship, Message, Notification, Profile, Song, Top10Comment,
    Top10Entry, Top10Reaction, User,
)
from app.mail import MailDeliveryError, get_mailer
from app.main import app

URL = "/api/v1/privacy/export"


class RecordingMailer:
    def __init__(self, fail=False):
        self.fail = fail
        self.recipients = []

    def send_export_confirmation(self, recipient):
        self.recipients.append(recipient)
        if self.fail:
            raise MailDeliveryError("private SMTP failure details")


@pytest.fixture
def mailer(client):
    fake = RecordingMailer()
    app.dependency_overrides[get_mailer] = lambda: fake
    return fake


def make_user(session, email, name):
    user = User(email=email, password_hash=f"secret-hash-{name}")
    user.profile = Profile(display_name=name, bio=f"{name}'s biography")
    session.add(user)
    session.flush()
    return user


def log_in(session, client, user):
    client.cookies.set(SESSION_COOKIE_NAME, start_session(session, user))
    session.commit()


def test_anonymous_export_is_refused_without_sending_email(client, mailer):
    response = client.post(URL)
    assert response.status_code == 401
    assert mailer.recipients == []


def test_empty_export_is_readable_versioned_and_delivered_to_account_email(session, client, mailer):
    alice = make_user(session, "alice@privacy.test", "Alice")
    log_in(session, client, alice)

    response = client.post(URL)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"] == 'attachment; filename="myplaylist-data.json"'
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-confirmation-email"] == "sent"
    assert response.content.endswith(b"\n")
    assert b"\n  \"account\"" in response.content
    exported = json.loads(response.content)
    assert exported["format_version"] == 3
    assert exported["exported_at"]
    assert exported["account"]["email"] == "alice@privacy.test"
    assert set(exported["account"]) == {
        "id", "email", "is_verified", "failed_login_count", "locked_until",
        "deleted_at", "created_at", "updated_at",
    }
    assert exported["profile"]["display_name"] == "Alice"
    assert exported["deletion_request"] is None
    for section in ("top10", "friendships", "blocks", "authored_comments", "reactions", "received_notifications", "messages"):
        assert exported[section] == []
    assert mailer.recipients == ["alice@privacy.test"]


def test_populated_export_is_scoped_and_excludes_secrets(session, client, mailer):
    alice = make_user(session, "alice@privacy.test", "Álice")
    bob = make_user(session, "bob@privacy.test", "Bob")
    carol = make_user(session, "carol@privacy.test", "Carol")
    alice_id, bob_id, carol_id = alice.id, bob.id, carol.id
    song = Song(provider="spotify", provider_id="track-one", title="Café", artist="Artist", metadata_={"internal_secret": "song-private"})
    session.add(song)
    session.flush()
    session.add_all([
        Top10Entry(user_id=alice_id, song_id=song.id, rank=1),
        Friendship(requester_id=alice_id, addressee_id=bob_id, status="accepted"),
        Block(blocker_id=alice_id, blocked_id=carol_id),
        Block(blocker_id=carol_id, blocked_id=alice_id),
        Top10Comment(top10_owner_id=bob_id, author_id=alice_id, body="My own comment"),
        Top10Comment(top10_owner_id=alice_id, author_id=bob_id, body="Other user's private comment"),
        Top10Reaction(top10_owner_id=bob_id, author_id=alice_id, reaction="like"),
        Top10Reaction(top10_owner_id=alice_id, author_id=bob_id, reaction="dislike"),
        Notification(recipient_id=alice_id, actor_id=bob_id, event_type="comment.created", message="Unexpected private text", event_key="private:source:1"),
        Notification(recipient_id=bob_id, actor_id=alice_id, event_type="comment.created", message="Bob private notification", event_key="private:source:2"),
    ])
    log_in(session, client, alice)

    response = client.post(URL, params={"user_id": bob_id}, json={"user_id": bob_id})
    assert response.status_code == 200
    body = response.text
    exported = response.json()
    assert exported["account"]["id"] == alice_id
    assert exported["profile"]["display_name"] == "Álice"
    assert exported["top10"][0]["song"]["title"] == "Café"
    assert len(exported["friendships"]) == 1
    assert exported["friendships"][0]["other_user_id"] == bob_id
    assert exported["friendships"][0]["direction"] == "sent"
    assert exported["friendships"][0]["status"] == "accepted"
    assert [row["blocked_user_id"] for row in exported["blocks"]] == [carol_id]
    assert [row["body"] for row in exported["authored_comments"]] == ["My own comment"]
    assert [row["reaction"] for row in exported["reactions"]] == ["like"]
    assert exported["received_notifications"][0]["message"] == "Someone commented on your Top 10."
    assert set(exported["received_notifications"][0]) == {"id", "event_type", "message", "created_at", "read_at"}
    assert len(exported["received_notifications"]) == 1
    for private in (
        "bob@privacy.test", "carol@privacy.test", "secret-hash-Álice",
        "Other user's private comment", "Bob private notification",
        "Unexpected private text", "private:source", "song-private",
        "token_hash", "password_hash", "event_key", "actor_id",
    ):
        assert private not in body
    assert mailer.recipients == ["alice@privacy.test"]

    client.cookies.set(SESSION_COOKIE_NAME, start_session(session, bob))
    session.commit()
    bob_export = client.post(URL).json()
    assert bob_export["account"]["id"] == bob_id
    assert bob_export["account"]["email"] == "bob@privacy.test"
    assert "My own comment" not in json.dumps(bob_export)
    assert mailer.recipients == ["alice@privacy.test", "bob@privacy.test"]


def test_message_export_includes_both_directions_once_and_excludes_other_conversations(session, client, mailer):
    alice = make_user(session, "alice@privacy.test", "Alice")
    bob = make_user(session, "bob@privacy.test", "Bob")
    carol = make_user(session, "carol@privacy.test", "Carol")
    dave = make_user(session, "dave@privacy.test", "Dave")
    alice_id, bob_id, carol_id, dave_id = alice.id, bob.id, carol.id, dave.id
    rows = [
        Message(sender_id=alice_id, recipient_id=bob_id, body="Hello Bob 🎵"),
        Message(sender_id=bob_id, recipient_id=alice_id, body="Hello Alice"),
        Message(sender_id=alice_id, recipient_id=carol_id, body="Hello Carol"),
        Message(sender_id=carol_id, recipient_id=alice_id, body="Hi Alice"),
        Message(sender_id=bob_id, recipient_id=carol_id, body="Bob and Carol secret"),
        Message(sender_id=dave_id, recipient_id=bob_id, body="Dave and Bob secret"),
    ]
    session.add_all(rows)
    session.flush()
    expected = {row.id for row in rows[:4]}
    unrelated = {row.id for row in rows[4:]}
    log_in(session, client, alice)

    response = client.post(URL, params={"user_id": bob_id}, json={"user_id": bob_id})

    assert response.status_code == 200
    exported = response.json()
    messages = exported["messages"]
    assert len(messages) == 4
    assert {row["id"] for row in messages} == expected
    assert not ({row["id"] for row in messages} & unrelated)
    assert {row["body"] for row in messages} == {
        "Hello Bob 🎵", "Hello Alice", "Hello Carol", "Hi Alice",
    }
    assert all(set(row) == {"id", "sender_id", "recipient_id", "body", "created_at"} for row in messages)
    assert all(row["created_at"] and row["created_at"].endswith("+00:00") for row in messages)
    assert all(alice_id in (row["sender_id"], row["recipient_id"]) for row in messages)
    assert "Bob and Carol secret" not in response.text
    assert "Dave and Bob secret" not in response.text
    assert "password_hash" not in response.text
    assert mailer.recipients == ["alice@privacy.test"]

    log_in(session, client, bob)
    bob_messages = client.post(URL).json()["messages"]
    assert {row["id"] for row in bob_messages} == {rows[0].id, rows[1].id, rows[4].id, rows[5].id}
    assert all(bob_id in (row["sender_id"], row["recipient_id"]) for row in bob_messages)


def test_email_failure_still_returns_export_without_logging_sensitive_details(session, client, mailer, caplog):
    alice = make_user(session, "alice@privacy.test", "Alice")
    log_in(session, client, alice)
    mailer.fail = True

    response = client.post(URL)

    assert response.status_code == 200
    assert response.json()["account"]["email"] == "alice@privacy.test"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-confirmation-email"] == "failed"
    assert "content-disposition" in response.headers
    assert "private SMTP failure details" not in caplog.text
    assert "alice@privacy.test" not in caplog.text
    assert "Data export confirmation email delivery failed" in caplog.text
    assert mailer.recipients == ["alice@privacy.test"]
