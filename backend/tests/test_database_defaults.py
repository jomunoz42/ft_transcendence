"""Defaults live in the database, not only in Python.

A teammate's seed script or a psql session inserts with plain SQL, so the
database itself must fill in every NOT NULL column that has a default.
"""

from sqlalchemy import text


def test_a_user_inserted_with_plain_sql_gets_the_defaults(session):
    user_id = session.scalar(
        text("INSERT INTO users (email, password_hash) VALUES ('sql@x.com', 'hash') RETURNING id")
    )
    session.execute(text("INSERT INTO profiles (user_id, display_name) VALUES (:id, 'SQL')"), {"id": user_id})

    user = session.execute(
        text("SELECT is_verified, failed_login_count FROM users WHERE id = :id"), {"id": user_id}
    ).one()
    profile = session.execute(
        text("SELECT is_top10_public, is_online FROM profiles WHERE user_id = :id"), {"id": user_id}
    ).one()
    assert tuple(user) == (False, 0)
    assert tuple(profile) == (False, False)


def test_a_friendship_inserted_with_plain_sql_starts_pending(session):
    ids = [
        session.scalar(text(f"INSERT INTO users (email, password_hash) VALUES ('{n}@x.com', 'h') RETURNING id"))
        for n in ("one", "two")
    ]

    status = session.scalar(
        text("INSERT INTO friendships (requester_id, addressee_id) VALUES (:a, :b) RETURNING status"),
        {"a": ids[0], "b": ids[1]},
    )

    assert status == "pending"


def test_a_song_inserted_with_plain_sql_gets_empty_metadata(session):
    metadata = session.scalar(
        text(
            "INSERT INTO songs (provider, provider_id, title, artist)"
            " VALUES ('manual', 'sql-1', 'Song', 'Artist') RETURNING metadata"
        )
    )

    assert metadata == {}
