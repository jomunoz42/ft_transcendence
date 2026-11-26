"""The app talks to PostgreSQL only through the SQLAlchemy ORM, and what it writes reads back through the model relationships (#58)."""

import ast
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import User
from app.main import app

API = "/api/v1"
APP_DIR = Path(__file__).resolve().parent.parent / "app"
SQL_STATEMENT = re.compile(r"\s*(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|DROP|ALTER|TRUNCATE)\b", re.IGNORECASE)
DRIVER_CALLS = {"exec_driver_sql", "cursor"}
DRIVERS = ("psycopg", "psycopg2", "asyncpg")
ALLOWED = {("main.py", "health", "SELECT 1")}  # /health connection check, reads no data


def raw_sql(source: str, name: str) -> list[tuple[str, str, str]]:
    """Every (file, enclosing function, SQL or call) in this source that goes past the ORM, except the allowed ones.

    Works on the syntax tree, so line breaks and layout inside a call cannot hide it.
    text() with a constant that is not a statement (server_default=text("false")) is fine;
    text() with anything built at run time is flagged, since it cannot be checked.
    """
    found = []

    def visit(node, function):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = node.name
        if isinstance(node, ast.Call):
            called = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if called == "text" and node.args:
                arg = node.args[0]
                sql = arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else ast.unparse(arg)
                if not isinstance(arg, ast.Constant) or SQL_STATEMENT.match(sql):
                    found.append((name, function, sql.strip()))
            elif called in DRIVER_CALLS:
                found.append((name, function, called))
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            found.extend((name, function, f"import {m}") for m in modules if m.split(".")[0] in DRIVERS)
        for child in ast.iter_child_nodes(node):
            visit(child, function)

    visit(ast.parse(source), "<module>")
    return [hit for hit in found if hit not in ALLOWED]


def test_the_app_sends_no_raw_sql():
    hits = []
    for path in sorted(APP_DIR.rglob("*.py")):
        hits += raw_sql(path.read_text(), path.relative_to(APP_DIR).as_posix())
    assert hits == []


@pytest.mark.parametrize("source", [
    'session.execute(text(\n    "SELECT * FROM users"\n))',
    'session.execute(sa.text("""\n    delete from users\n"""))',
    'session.execute(text(f"SELECT {column} FROM users"))',
    'session.execute(text(query))',
    'connection.exec_driver_sql("SELECT 1")',
    'raw = connection.connection.cursor()',
    'import psycopg2',
    'from psycopg import sql',
    'def not_health():\n    session.execute(text("SELECT 1"))',
], ids=["multiline", "triple-quoted lowercase", "f-string", "variable", "exec_driver_sql", "cursor", "import psycopg2", "from psycopg", "SELECT 1 outside health"])
def test_the_guard_catches_raw_sql_however_it_is_written(source):
    assert raw_sql(source, "main.py") != []


@pytest.mark.parametrize("source", [
    'is_verified = mapped_column(Boolean, server_default=text("false"))',
    'def health():\n    session.execute(text("SELECT 1"))',
    'session.scalars(select(User).where(User.id == 1))',
], ids=["server_default", "health check", "ORM select"])
def test_the_guard_lets_the_orm_through(source):
    assert raw_sql(source, "main.py") == []


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
