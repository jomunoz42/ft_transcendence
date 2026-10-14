"""Tests for the current_user dependency (auth issue #15).

The seam is a route that depends on current_user, so each test builds a tiny app
with one protected route instead of going through the real routers.
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.current_user import SESSION_COOKIE, current_user
from app.auth.registration import register_user
from app.auth.sessions import end_session, start_session
from app.db import get_session
from app.db.models import User


@pytest.fixture
def client(session):
    app = FastAPI()

    @app.get("/protected")
    def protected(user: User = Depends(current_user)):
        return {"id": user.id}

    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, base_url="https://testserver")


def test_a_request_without_a_session_cookie_is_refused(client):
    response = client.get("/protected")

    assert response.status_code == 401


def test_a_valid_session_cookie_gives_the_route_its_user(client, session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    client.cookies.set(SESSION_COOKIE, start_session(session, alice))

    response = client.get("/protected")

    assert response.status_code == 200
    assert response.json() == {"id": alice.id}


def test_a_cookie_from_an_ended_session_is_refused(client, session):
    alice = register_user(session, "alice@x.com", "hunter22", "Alice")
    token = start_session(session, alice)
    client.cookies.set(SESSION_COOKIE, token)
    end_session(session, token)

    response = client.get("/protected")

    assert response.status_code == 401
