"""Songs and Top 10 entries, verified against real Postgres."""

import pytest
from sqlalchemy import case, delete, select, update
from sqlalchemy.exc import IntegrityError

from app.db.models import Song, Top10Entry, User


def make_user(session, email="ranker@myplaylist.test"):
    user = User(email=email, password_hash="hash")
    session.add(user)
    session.flush()
    return user


def make_song(session, provider_id, title="Song"):
    song = Song(provider="spotify", provider_id=provider_id, title=title, artist="Artist")
    session.add(song)
    session.flush()
    return song


def test_a_user_stores_a_full_top10_and_reads_it_back_in_rank_order(session):
    user = make_user(session)
    # Inserted in reverse so reading back in order proves the ranking, not insertion order.
    for rank in range(10, 0, -1):
        song = make_song(session, provider_id=f"track-{rank}", title=f"Song {rank}")
        session.add(Top10Entry(user_id=user.id, song_id=song.id, rank=rank))
    session.flush()
    session.expire_all()

    entries = session.scalars(
        select(Top10Entry).where(Top10Entry.user_id == user.id).order_by(Top10Entry.rank)
    ).all()

    assert [e.rank for e in entries] == list(range(1, 11))
    assert [e.song.title for e in entries] == [f"Song {n}" for n in range(1, 11)]


@pytest.mark.parametrize("rank", [0, 11])
def test_a_rank_outside_1_to_10_is_rejected(session, rank):
    user = make_user(session)
    song = make_song(session, provider_id="track-1")

    session.add(Top10Entry(user_id=user.id, song_id=song.id, rank=rank))

    with pytest.raises(IntegrityError):
        session.flush()


def test_a_user_cannot_put_two_songs_at_the_same_rank(session):
    user = make_user(session)
    first = make_song(session, provider_id="track-1")
    second = make_song(session, provider_id="track-2")
    session.add(Top10Entry(user_id=user.id, song_id=first.id, rank=1))
    session.flush()

    session.add(Top10Entry(user_id=user.id, song_id=second.id, rank=1))

    with pytest.raises(IntegrityError):
        session.flush()


def two_ranked_entries(session):
    """Return one user's entries at ranks 1 and 2, flushed so they have ids."""
    user = make_user(session)
    first = Top10Entry(user_id=user.id, song_id=make_song(session, "track-1").id, rank=1)
    second = Top10Entry(user_id=user.id, song_id=make_song(session, "track-2").id, rank=2)
    session.add_all([first, second])
    session.flush()
    return user, first, second


def set_ranks(session, new_rank_by_id):
    """Give several entries their new ranks in one ORM UPDATE statement."""
    session.execute(
        update(Top10Entry)
        .where(Top10Entry.id.in_(new_rank_by_id))
        .values(rank=case(new_rank_by_id, value=Top10Entry.id))
    )


def test_two_entries_swap_ranks_in_one_update_and_keep_their_ids(session):
    user, first, second = two_ranked_entries(session)

    set_ranks(session, {first.id: 2, second.id: 1})
    session.expire_all()

    rows = session.execute(
        select(Top10Entry.id, Top10Entry.rank).where(Top10Entry.user_id == user.id).order_by(Top10Entry.id)
    ).all()
    assert rows == [(first.id, 2), (second.id, 1)]


def test_one_update_still_cannot_leave_two_songs_at_the_same_rank(session):
    _, first, second = two_ranked_entries(session)

    with pytest.raises(IntegrityError):
        set_ranks(session, {first.id: 3, second.id: 3})


def test_a_user_cannot_rank_the_same_song_twice(session):
    user = make_user(session)
    song = make_song(session, provider_id="track-1")
    session.add(Top10Entry(user_id=user.id, song_id=song.id, rank=1))
    session.flush()

    session.add(Top10Entry(user_id=user.id, song_id=song.id, rank=2))

    with pytest.raises(IntegrityError):
        session.flush()


def test_the_same_provider_track_cannot_be_stored_twice(session):
    make_song(session, provider_id="track-1")

    session.add(Song(provider="spotify", provider_id="track-1", title="Copy", artist="Artist"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_a_song_still_in_a_top10_cannot_be_deleted(session):
    user = make_user(session)
    song = make_song(session, provider_id="track-1")
    session.add(Top10Entry(user_id=user.id, song_id=song.id, rank=1))
    session.flush()

    # A direct statement, not session.delete(), so the database's ON DELETE
    # RESTRICT is what stops it rather than anything SQLAlchemy does in Python.
    with pytest.raises(IntegrityError):
        session.execute(delete(Song).where(Song.id == song.id))
