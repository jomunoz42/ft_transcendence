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
from app.db.models import Base, Friendship, User
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

    all_at_once([lambda b=browser(): b.post(f"{API}/auth/login", json=wrong) for _ in range(BROWSERS)])

    assert browser().post(f"{API}/auth/login", json={"email": "alice@x.com", "password": "hunter22"}).status_code == 401
