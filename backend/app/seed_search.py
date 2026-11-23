"""Opt-in offline catalog demo: python -m app.seed_search.

Only insert missing demo provider IDs. Never update/delete existing songs,
accounts or playlists. Not called by application startup or migrations.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.db.models import Song

DEMO_PREFIX = "search-demo-v1-"


def seed_search(session: Session) -> int:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(60):
        rows.append({
            "provider": "manual",
            "provider_id": f"{DEMO_PREFIX}{index:03d}",
            # Paired titles and dates exercise the unique ID tie-breaker.
            "title": f"Demo Track {index // 2 + 1:02d}",
            "artist": "Demo Ensemble" if index < 40 else "Demo Quartet",
            "album": None if index >= 50 else ("Demo Sessions" if index < 30 else "Demo Nights"),
            "duration_ms": None if index >= 50 else 150_000 + index * 1000,
            "created_at": start + timedelta(days=index // 2),
            "updated_at": start + timedelta(days=index // 2),
            "metadata_": {},
        })
    statement = insert(Song).values(rows).on_conflict_do_nothing(
        index_elements=[Song.provider, Song.provider_id],
    ).returning(Song.id)
    return len(session.scalars(statement).all())


if __name__ == "__main__":
    with SessionLocal.begin() as session:
        added = seed_search(session)
    print(f"Added {added} demo songs. Existing records were preserved.")
