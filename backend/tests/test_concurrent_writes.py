"""The same write fired from several browsers at once, through the real app, with real commits (#50).

Each test owns a temporary PostgreSQL schema, so the requests run in separate
connections and transactions, like production, without touching other tests' data.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db import engine, get_session
from app.db.models import Base, Friendship, Top10Entry, User
from app.main import app

API = "/api/v1"
BROWSERS = 5


@pytest.fixture
def isolated_db():
    """A fresh schema the app commits into for real; dropped afterwards. Yields a session factory on it."""
    schema = "test_concurrent_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    factory = sessionmaker(bind=isolated)

    def request_session():
        with factory() as session:
            yield session

    try:
        Base.metadata.create_all(isolated)
        app.dependency_overrides[get_session] = request_session
        yield factory
    finally:
        app.dependency_overrides.clear()
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


def browser() -> TestClient:
    """A browser with its own cookies that sees a server error as a 500 response."""
    return TestClient(app, base_url="https://testserver", raise_server_exceptions=False)


def all_at_once(calls):
    """Run each call in its own thread, released together; their results in order."""
    start = Barrier(len(calls))

    def run(call):
        start.wait()
        return call()

    with ThreadPoolExecutor(len(calls)) as pool:
        return list(pool.map(run, calls))


def log_in(email: str) -> tuple[TestClient, int]:
    """A browser with a new account for `email` registered and logged in, and its id."""
    b = browser()
    user_id = b.post(f"{API}/auth/register", json={"email": email, "password": "hunter22", "display_name": email}).json()["id"]
    b.post(f"{API}/auth/login", json={"email": email, "password": "hunter22"})
    return b, user_id


def test_the_same_email_registered_from_five_browsers_at_once_creates_one_account(isolated_db):
    body = {"email": "alice@x.com", "password": "hunter22", "display_name": "Alice"}
    browsers = [browser() for _ in range(BROWSERS)]

    responses = all_at_once([lambda b=b: b.post(f"{API}/auth/register", json=body) for b in browsers])

    assert sorted(r.status_code for r in responses) == [201] + [409] * (BROWSERS - 1)
    with isolated_db() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1


def test_two_users_asking_each_other_at_once_end_up_friends_in_one_row(isolated_db):
    alice, alice_id = log_in("alice@x.com")
    bob, bob_id = log_in("bob@x.com")

    responses = all_at_once([
        lambda: alice.post(f"{API}/friends/request/{bob_id}"),
        lambda: bob.post(f"{API}/friends/request/{alice_id}"),
    ])

    assert [r.status_code for r in responses] == [200, 200]
    assert sorted(r.json()["status"] for r in responses) == ["accepted", "pending"]
    with isolated_db() as session:
        assert session.scalars(select(Friendship.status)).all() == ["accepted"]


def test_five_wrong_passwords_at_once_still_lock_the_account(isolated_db):
    log_in("alice@x.com")
    wrong = {"email": "alice@x.com", "password": "wrong-pass"}

    responses = all_at_once([lambda b=browser(): b.post(f"{API}/auth/login", json=wrong) for _ in range(BROWSERS)])

    assert [r.status_code for r in responses] == [401] * BROWSERS
    with isolated_db() as session:
        user = session.scalars(select(User).where(User.email == "alice@x.com")).one()
        assert session.scalar(select(User.locked_until > func.now()).where(User.id == user.id))
        assert user.failed_login_count == 0
    assert browser().post(f"{API}/auth/login", json={"email": "alice@x.com", "password": "hunter22"}).status_code == 401


def add_song(b: TestClient, user_id: int, rank: int) -> int:
    """Put a new song at `rank` in this user's Top 10 through the API; the entry id."""
    song = {"provider_id": f"track-{rank}", "title": f"Song {rank}", "artist": "Artist"}
    return b.post(f"{API}/profiles/{user_id}/top10", json={"song": song, "rank": rank}).json()["id"]


def move(b: TestClient, user_id: int, entry_id: int, rank: int):
    """Ask the API to move one Top 10 entry to `rank`."""
    return b.post(f"{API}/profiles/{user_id}/top10/{entry_id}", json={"rank": rank})


def ranks_by_id(factory) -> dict[int, int]:
    """Every committed Top 10 entry as {id: rank}."""
    with factory() as session:
        return dict(session.execute(select(Top10Entry.id, Top10Entry.rank)).all())


def test_moving_a_song_onto_a_taken_rank_swaps_the_two_and_keeps_their_ids(isolated_db):
    alice, alice_id = log_in("alice@x.com")
    first, second = add_song(alice, alice_id, 1), add_song(alice, alice_id, 2)

    response = move(alice, alice_id, first, 2)

    assert (response.status_code, response.json()["id"], response.json()["rank"]) == (200, first, 2)
    assert ranks_by_id(isolated_db) == {first: 2, second: 1}


def test_two_opposite_swaps_at_once_do_not_deadlock(isolated_db):
    alice, alice_id = log_in("alice@x.com")
    first, second = add_song(alice, alice_id, 1), add_song(alice, alice_id, 2)

    responses = all_at_once([lambda: move(alice, alice_id, first, 2), lambda: move(alice, alice_id, second, 1)])

    assert [r.status_code for r in responses] == [200, 200]
    assert ranks_by_id(isolated_db) == {first: 2, second: 1}


def test_two_songs_moved_onto_the_same_empty_rank_at_once_keep_ranks_unique(isolated_db):
    alice, alice_id = log_in("alice@x.com")
    first, second = add_song(alice, alice_id, 1), add_song(alice, alice_id, 2)

    responses = all_at_once([lambda: move(alice, alice_id, first, 5), lambda: move(alice, alice_id, second, 5)])

    assert [r.status_code for r in responses] == [200, 200]
    assert ranks_by_id(isolated_db) in ({first: 5, second: 1}, {first: 2, second: 5})


def test_a_move_and_an_add_onto_the_same_empty_rank_at_once_give_no_server_error(isolated_db):
    alice, alice_id = log_in("alice@x.com")
    first = add_song(alice, alice_id, 1)
    song = {"provider_id": "track-new", "title": "New", "artist": "Artist"}

    responses = all_at_once([
        lambda: move(alice, alice_id, first, 5),
        lambda: alice.post(f"{API}/profiles/{alice_id}/top10", json={"song": song, "rank": 5}),
    ])

    assert sorted(r.status_code for r in responses) in ([200, 200], [200, 409])
    ranks = list(ranks_by_id(isolated_db).values())
    assert len(ranks) == len(set(ranks))
