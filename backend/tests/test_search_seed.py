"""The opt-in seed is offline, repeatable and preserves existing catalog records."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db.models import Song, Top10Entry, User
from app.seed_search import seed_search


@pytest.fixture
def demo_prefix(monkeypatch):
    # Keep tests independent of opt-in demo rows already present in the database.
    prefix = f"search-seed-test-{uuid4().hex}-"
    monkeypatch.setattr("app.seed_search.DEMO_PREFIX", prefix)
    return prefix


def test_seed_is_idempotent_and_preserves_existing_records(session, demo_prefix):
    existing = Song(provider="manual", provider_id="existing-test-song", title="Keep me", artist="Original")
    collision = Song(provider="manual", provider_id=f"{demo_prefix}000", title="Edited demo", artist="Original")
    user = User(email="seed-owner@example.test", password_hash="unused")
    session.add_all([existing, collision, user])
    session.flush()
    entry = Top10Entry(user_id=user.id, song_id=existing.id, rank=1)
    session.add(entry)
    session.flush()
    before = session.scalar(select(func.count()).select_from(Song))

    assert seed_search(session) == 59
    assert seed_search(session) == 0
    assert session.scalar(select(func.count()).select_from(Song)) == before + 59
    session.expire_all()
    assert session.get(Song, collision.id).title == "Edited demo"
    assert session.get(Song, existing.id).title == "Keep me"
    assert session.get(Top10Entry, entry.id).song_id == existing.id
    assert session.get(User, user.id).deleted_at is None


def test_seed_has_multiple_filtered_pages_and_nullable_fields(session, demo_prefix):
    assert seed_search(session) == 60
    rows = list(session.scalars(select(Song).where(Song.provider_id.startswith(demo_prefix))))
    assert len(rows) == 60
    assert sum(song.artist == "Demo Ensemble" for song in rows) == 40
    assert sum(song.artist == "Demo Ensemble" and song.album == "Demo Sessions" for song in rows) == 30
    assert sum(song.album is None and song.duration_ms is None for song in rows) == 10
    assert len({song.title for song in rows}) < len(rows)
