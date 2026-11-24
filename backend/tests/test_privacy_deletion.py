"""Confirmed deletion, PostgreSQL cascades, token controls and mail outcomes."""

import datetime
import re
from contextlib import nullcontext

import pytest
from sqlalchemy import select, text

from app import deletion
from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.sessions import start_session, user_for_token
from app.auth import websocket as websocket_auth
from app.db.models import (
    Block, DeletionRequest, Friendship, Notification, Profile, Song,
    Top10Comment, Top10Entry, Top10Reaction, User, UserSession,
)
from app.mail import MailDeliveryError, get_mailer
from app.main import app

REQUEST = "/api/v1/privacy/deletion-request"
CONFIRM = "/api/v1/privacy/deletion-confirm"


class RecordingMailer:
    def __init__(self):
        self.sent = []
        self.fail_request = False
        self.fail_completion = False
        self.unexpected_completion_error = False

    def send(self, recipient, subject, body):
        if self.fail_request and subject.startswith("Confirm"):
            raise MailDeliveryError("secret SMTP request error")
        if self.fail_completion and subject.startswith("Your"):
            raise MailDeliveryError("secret SMTP completion error")
        if self.unexpected_completion_error and subject.startswith("Your"):
            raise RuntimeError("unexpected private mail error")
        self.sent.append((recipient, subject, body))

    def send_export_confirmation(self, recipient):
        self.send(recipient, "Your MyPlaylist data export", "Export requested")


@pytest.fixture
def mailer(client, monkeypatch):
    fake = RecordingMailer()
    app.dependency_overrides[get_mailer] = lambda: fake
    monkeypatch.setenv("PRIVACY_TOKEN_SECRET", "ft57-test-only-secret-with-more-than-32-bytes")
    return fake


def make_user(session, email):
    user = User(email=email, password_hash="stored-password-hash")
    user.profile = Profile(display_name=email.split("@")[0])
    session.add(user)
    session.flush()
    return user


def log_in(session, client, user):
    token = start_session(session, user)
    client.cookies.set(SESSION_COOKIE_NAME, token)
    session.commit()
    return token


def request_token(client, mailer):
    response = client.post(REQUEST)
    assert response.status_code == 202
    assert response.headers["cache-control"] == "no-store"
    assert datetime.datetime.fromisoformat(response.json()["expires_at"]).tzinfo is not None
    assert response.json()["cooldown_seconds"] == 300
    body = mailer.sent[-1][2]
    found = re.search(r"confirm deletion:\n\n([A-Za-z0-9_.-]+)\n\n", body)
    assert found is not None
    token = found.group(1)
    assert token not in response.text
    return token


def confirm(client, token, phrase="DELETE"):
    return client.post(CONFIRM, json={"token": token, "confirmation": phrase})


def count_for(session, table, column, user_id):
    return session.scalar(text(f"SELECT count(*) FROM {table} WHERE {column} = :user_id"), {"user_id": user_id})


def test_both_endpoints_require_authentication(client, mailer):
    assert client.post(REQUEST).status_code == 401
    assert confirm(client, "not-a-token").status_code == 401
    assert mailer.sent == []


def test_request_without_confirm_or_with_wrong_phrase_does_not_delete(session, client, mailer):
    alice = make_user(session, "alice@deletion.test")
    alice_id = alice.id
    log_in(session, client, alice)
    token = request_token(client, mailer)
    assert client.delete("/api/v1/settings").status_code == 405
    assert confirm(client, token, "CANCEL").status_code == 422
    assert count_for(session, "users", "id", alice_id) == 1
    row = session.get(DeletionRequest, alice_id)
    assert row is not None
    assert token != row.token_hash
    assert len(row.token_hash) == 64
    exported = client.post("/api/v1/privacy/export")
    assert exported.status_code == 200
    assert exported.json()["deletion_request"]["requested_at"]
    assert exported.json()["deletion_request"]["expires_at"]
    assert token not in exported.text
    assert row.token_hash not in exported.text


def test_real_login_cookie_is_cleared_after_confirmation(session, client, mailer):
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "browser@deletion.test", "password": "browser-password", "display_name": "Browser"},
    )
    assert registered.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "browser@deletion.test", "password": "browser-password"},
    )
    assert login.status_code == 200
    assert SESSION_COOKIE_NAME in client.cookies
    token = request_token(client, mailer)
    assert confirm(client, token).status_code == 204
    assert SESSION_COOKIE_NAME not in client.cookies


def test_request_is_rate_limited_and_new_token_invalidates_old_one(session, client, mailer, monkeypatch):
    alice = make_user(session, "alice@deletion.test")
    log_in(session, client, alice)
    first = request_token(client, mailer)
    limited = client.post(REQUEST)
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0
    assert len(mailer.sent) == 1

    later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=6)
    monkeypatch.setattr(deletion, "now_utc", lambda: later)
    second = request_token(client, mailer)
    assert second != first
    assert confirm(client, first).status_code == 400
    assert confirm(client, second).status_code == 204


def test_new_request_cleans_other_expired_challenges_without_bypassing_cooldown(session, client, mailer):
    alice = make_user(session, "alice@deletion.test")
    bob = make_user(session, "bob@deletion.test")
    bob_id = bob.id
    old = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    session.add(DeletionRequest(
        user_id=bob_id, token_hash="old-hash", requested_at=old,
        expires_at=old + datetime.timedelta(minutes=15),
    ))
    log_in(session, client, alice)
    request_token(client, mailer)
    assert session.get(DeletionRequest, bob_id) is None
    assert client.post(REQUEST).status_code == 429
    assert count_for(session, "users", "id", bob_id) == 1


@pytest.mark.parametrize("bad_token", ["tampered", "truncated"])
def test_tampered_tokens_are_rejected(session, client, mailer, bad_token):
    alice = make_user(session, "alice@deletion.test")
    alice_id = alice.id
    log_in(session, client, alice)
    token = request_token(client, mailer)
    wrong = token[:-1] + ("x" if token[-1] != "x" else "y") if bad_token == "tampered" else token[:30]
    assert confirm(client, wrong).status_code == 400
    assert count_for(session, "users", "id", alice_id) == 1


def test_expiry_and_changed_email_invalidate_token(session, client, mailer, monkeypatch):
    alice = make_user(session, "alice@deletion.test")
    log_in(session, client, alice)
    token = request_token(client, mailer)
    alice.email = "changed@deletion.test"
    session.commit()
    assert confirm(client, token).status_code == 400

    alice.email = "alice@deletion.test"
    session.commit()
    later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=16)
    monkeypatch.setattr(deletion, "now_utc", lambda: later)
    assert confirm(client, token).status_code == 400
    assert count_for(session, "users", "id", alice.id) == 1


def test_token_cannot_be_used_from_another_account(session, client, mailer):
    alice = make_user(session, "alice@deletion.test")
    bob = make_user(session, "bob@deletion.test")
    alice_id, bob_id = alice.id, bob.id
    log_in(session, client, alice)
    token = request_token(client, mailer)
    log_in(session, client, bob)
    assert confirm(client, token).status_code == 400
    assert count_for(session, "users", "id", alice_id) == 1
    assert count_for(session, "users", "id", bob_id) == 1


def test_smtp_failure_does_not_create_a_usable_request(session, client, mailer, caplog):
    alice = make_user(session, "alice@deletion.test")
    alice_id = alice.id
    log_in(session, client, alice)
    mailer.fail_request = True
    response = client.post(REQUEST)
    assert response.status_code == 503
    assert session.get(DeletionRequest, alice_id) is None
    assert count_for(session, "users", "id", alice_id) == 1
    assert "secret SMTP request error" not in caplog.text
    assert "alice@deletion.test" not in caplog.text
    assert mailer.sent == []
    mailer.fail_request = False
    assert client.post(REQUEST).status_code == 202


def test_missing_signing_secret_does_not_issue_a_request(session, client, mailer, monkeypatch):
    alice = make_user(session, "alice@deletion.test")
    alice_id = alice.id
    log_in(session, client, alice)
    monkeypatch.delenv("PRIVACY_TOKEN_SECRET")
    assert client.post(REQUEST).status_code == 503
    assert session.get(DeletionRequest, alice_id) is None
    assert mailer.sent == []


def test_hard_delete_cascades_and_anonymizes_retained_notifications(session, client, mailer, monkeypatch):
    alice = make_user(session, "alice@deletion.test")
    bob = make_user(session, "bob@deletion.test")
    carol = make_user(session, "carol@deletion.test")
    alice_id, bob_id, carol_id = alice.id, bob.id, carol.id
    song = Song(provider="spotify", provider_id="shared-track", title="Shared", artist="Artist")
    session.add(song)
    session.flush()
    song_id = song.id
    session.add_all([
        Top10Entry(user_id=alice_id, song_id=song_id, rank=1),
        Top10Entry(user_id=bob_id, song_id=song_id, rank=1),
        Friendship(requester_id=alice_id, addressee_id=bob_id, status="accepted"),
        Block(blocker_id=alice_id, blocked_id=carol_id),
        Block(blocker_id=carol_id, blocked_id=alice_id),
        Top10Comment(top10_owner_id=bob_id, author_id=alice_id, body="Alice's comment"),
        Top10Comment(top10_owner_id=alice_id, author_id=bob_id, body="Bob's comment"),
        Top10Reaction(top10_owner_id=bob_id, author_id=alice_id, reaction="like"),
        Top10Reaction(top10_owner_id=alice_id, author_id=bob_id, reaction="like"),
        Notification(recipient_id=alice_id, actor_id=bob_id, event_type="comment.created", message="My inbox", event_key="mine:1"),
        Notification(recipient_id=bob_id, actor_id=alice_id, event_type="comment.created", message="Alice personal data", event_key=f"alice:{alice_id}:secret"),
        Notification(recipient_id=bob_id, actor_id=carol_id, event_type="friend_request.created", message="Unrelated", event_key="unrelated:1"),
    ])
    session.flush()
    first_token = log_in(session, client, alice)
    second_token = start_session(session, alice)
    bob_token = start_session(session, bob)
    session.commit()
    token = request_token(client, mailer)

    response = confirm(client, token)

    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["set-cookie"].startswith(f"{SESSION_COOKIE_NAME}=\"\";")
    assert "Max-Age=0" in response.headers["set-cookie"]
    for table, column in (
        ("users", "id"), ("profiles", "user_id"), ("top10_entries", "user_id"),
        ("friendships", "requester_id"), ("friendships", "addressee_id"),
        ("blocks", "blocker_id"), ("blocks", "blocked_id"),
        ("top10_comments", "author_id"), ("top10_comments", "top10_owner_id"),
        ("top10_reactions", "author_id"), ("top10_reactions", "top10_owner_id"),
        ("sessions", "user_id"), ("notifications", "recipient_id"),
        ("privacy_deletion_requests", "user_id"),
    ):
        assert count_for(session, table, column, alice_id) == 0, (table, column)
    assert count_for(session, "users", "id", bob_id) == 1
    assert count_for(session, "songs", "id", song_id) == 1
    assert count_for(session, "top10_entries", "user_id", bob_id) == 1
    assert user_for_token(session, first_token) is None
    assert user_for_token(session, second_token) is None
    assert user_for_token(session, bob_token) is not None
    # HTTP authorization checks the database on every request, even before
    # an existing WebSocket's next revalidation tick.
    client.cookies.set(SESSION_COOKIE_NAME, first_token)
    assert client.post("/api/v1/privacy/export").status_code == 401
    assert client.post("/api/v1/profiles/me", json={"display_name": "Ghost"}).status_code == 401
    client.cookies.set(SESSION_COOKIE_NAME, second_token)
    assert client.post("/api/v1/privacy/deletion-request").status_code == 401
    monkeypatch.setattr(websocket_auth, "SessionLocal", lambda: nullcontext(session))
    assert websocket_auth.authenticate_websocket(first_token) is None
    assert websocket_auth.authenticate_websocket(second_token) is None

    retained = session.scalars(select(Notification).where(Notification.recipient_id == bob_id).order_by(Notification.id)).all()
    assert len(retained) == 2
    anonymized, unrelated = retained
    assert anonymized.actor_id is None
    assert anonymized.event_key == f"gdpr:removed-actor:{anonymized.id}"
    assert anonymized.message == "Someone commented on your Top 10."
    assert unrelated.actor_id == carol_id
    assert unrelated.event_key == "unrelated:1"
    assert mailer.sent[-1][1] == "Your MyPlaylist account was deleted"
    assert confirm(client, token).status_code == 401  # no session remains for replay


def test_completion_email_failure_does_not_undo_deletion(session, client, mailer, caplog):
    alice = make_user(session, "alice@deletion.test")
    alice_id = alice.id
    log_in(session, client, alice)
    token = request_token(client, mailer)
    mailer.fail_completion = True
    assert confirm(client, token).status_code == 204
    assert count_for(session, "users", "id", alice_id) == 0
    assert "Account deletion completion email delivery failed" in caplog.text
    assert "secret SMTP completion error" not in caplog.text


def test_unexpected_post_commit_mail_error_still_reports_success(session, client, mailer, caplog):
    alice = make_user(session, "alice@deletion.test")
    alice_id = alice.id
    log_in(session, client, alice)
    token = request_token(client, mailer)
    mailer.unexpected_completion_error = True
    assert confirm(client, token).status_code == 204
    assert count_for(session, "users", "id", alice_id) == 0
    assert "unexpected private mail error" not in caplog.text


def test_database_failure_rolls_back_notification_changes_and_user_delete(session, client, mailer, monkeypatch):
    alice = make_user(session, "alice@deletion.test")
    bob = make_user(session, "bob@deletion.test")
    alice_id = alice.id
    note = Notification(recipient_id=bob.id, actor_id=alice_id, event_type="comment.created", message="Original", event_key="original:1")
    session.add(note)
    log_in(session, client, alice)
    note_id = note.id
    token = request_token(client, mailer)

    def fail_delete(*_args):
        raise RuntimeError("forced database failure")

    monkeypatch.setattr(deletion, "delete_user_row", fail_delete)
    with pytest.raises(RuntimeError, match="forced database failure"):
        confirm(client, token)
    session.expire_all()
    assert count_for(session, "users", "id", alice_id) == 1
    stored = session.get(Notification, note_id)
    assert stored.actor_id == alice_id
    assert stored.event_key == "original:1"
    assert stored.message == "Original"
    assert len(mailer.sent) == 1  # no completion email
