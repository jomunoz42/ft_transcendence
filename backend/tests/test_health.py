"""Ticket 02: /health must report whether the backend can actually reach the database.

The seam under test is the HTTP endpoint, not the session module behind it.
"""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import get_session
from app.main import app

client = TestClient(app)


def test_health_reports_ok_when_the_database_is_reachable():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_failure_when_the_database_is_unreachable():
    """A readiness check that stays green while the database is down is worthless."""
    dead_engine = create_engine("postgresql+psycopg2://nobody@127.0.0.1:1/nothing")
    DeadSession = sessionmaker(bind=dead_engine)

    def dead_session():
        session = DeadSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = dead_session
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unreachable"}
