"""The app talks to PostgreSQL only through the SQLAlchemy ORM, and what it writes reads back through the model relationships (#58)."""

import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import User
from app.main import app

API = "/api/v1"
APP_DIR = Path(__file__).resolve().parent.parent / "app"
RAW_SQL = re.compile(
    r"""text\(\s*["'](SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|DROP|ALTER|TRUNCATE)\b|exec_driver_sql|\.cursor\(|import psycopg""",
    re.IGNORECASE,
)
ALLOWED = {("main.py", 'session.execute(text("SELECT 1"))')}  # /health connection check, reads no data


def raw_sql_lines() -> list[tuple[str, str]]:
    """Every (file, line) under app/ that sends SQL past the ORM, except the allowed ones."""
    found = []
    for path in sorted(APP_DIR.rglob("*.py")):
        name = path.relative_to(APP_DIR).as_posix()
        for line in path.read_text().splitlines():
            if RAW_SQL.search(line) and (name, line.strip()) not in ALLOWED:
                found.append((name, line.strip()))
    return found


def test_the_app_sends_no_raw_sql():
    assert raw_sql_lines() == []


def test_what_the_app_writes_reads_back_through_the_model_relationships(client, session):
    bob = TestClient(app, base_url="https://testserver")
    alice_id = client.post(f"{API}/auth/register", json={"email": "alice@x.com", "password": "hunter22", "display_name": "Alice"}).json()["id"]
    bob_id = bob.post(f"{API}/auth/register", json={"email": "bob@x.com", "password": "hunter33", "display_name": "Bob"}).json()["id"]
    client.post(f"{API}/auth/login", json={"email": "alice@x.com", "password": "hunter22"})
    bob.post(f"{API}/auth/login", json={"email": "bob@x.com", "password": "hunter33"})
    client.post(f"{API}/friends/request/{bob_id}")
    bob.post(f"{API}/friends/accept/{alice_id}")
    bob.post(f"{API}/profiles/{alice_id}/comments", json={"body": "great taste"})

    alice = session.scalars(select(User).where(User.id == alice_id)).one()

    assert alice.profile.display_name == "Alice"
    assert [(f.addressee.email, f.status) for f in alice.sent_requests] == [("bob@x.com", "accepted")]
    assert [(c.body, c.top10_owner_id) for c in alice.sent_requests[0].addressee.comments] == [("great taste", alice_id)]
    assert len(alice.sessions) == 1
