"""Test harness for the database layer.

Tests run against the real Postgres container — the spec rules out mocking the
database, since the constraints being verified are enforced by Postgres itself
and a mock would happily accept what the real database rejects.

Each test runs inside a transaction that is rolled back afterwards, so tests see
a clean database without the schema being rebuilt between them. Code under test
may commit: each commit only releases a savepoint inside that transaction.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import engine, get_session
from app.main import app
from known_bugs import KNOWN_BUGS


def pytest_collection_modifyitems(items):
    """Mark each test listed in known_bugs.py as a strict xfail that names its owner."""
    for item in items:
        if item.nodeid in KNOWN_BUGS:
            owner, why = KNOWN_BUGS[item.nodeid]
            item.add_marker(pytest.mark.xfail(strict=True, reason=f"{owner}: {why}"))


def pytest_terminal_summary(terminalreporter):
    """List the known bugs still failing, grouped by owner, at the end of the run."""
    by_owner = {}
    for report in terminalreporter.stats.get("xfailed", []):
        if report.nodeid in KNOWN_BUGS:
            owner, why = KNOWN_BUGS[report.nodeid]
            by_owner.setdefault(owner, []).append(why)
    if by_owner:
        terminalreporter.section("known bugs by owner (tests/known_bugs.py)")
        for owner, bugs in sorted(by_owner.items()):
            terminalreporter.line(f"{owner}: {len(bugs)}")
            for why in bugs:
                terminalreporter.line(f"  - {why}")


@pytest.fixture
def anyio_backend():
    # The WebSocket ASGI harness and application run on asyncio.
    return "asyncio"


@pytest.fixture
def session():
    connection = engine.connect()
    transaction = connection.begin()
    db_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield db_session
    finally:
        db_session.close()
        if transaction.is_active:  # an IntegrityError already rolled it back
            transaction.rollback()
        connection.close()


@pytest.fixture
def client(session):
    """HTTP client for the real app, sharing the test's session; https so Secure cookies come back.

    Like production, each request's uncommitted work is dropped when it ends,
    so commit any setup made directly through `session` before calling the client.
    """

    def request_session():
        try:
            yield session
        finally:
            session.rollback()

    app.dependency_overrides[get_session] = request_session
    try:
        yield TestClient(app, base_url="https://testserver")
    finally:
        app.dependency_overrides.clear()
