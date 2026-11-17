"""The settings routes under /api/v1/settings, called through the real app."""

import pytest
from sqlalchemy.orm import Session

from app.db import engine

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
SETTINGS = "/api/v1/settings"
ALICE = {"email": "alice@x.com", "password": "hunter22", "display_name": "Alice"}


@pytest.fixture
def session():
    """The conftest session, but keeping loaded fields after commit like the app's SessionLocal (expire_on_commit=False)."""
    connection = engine.connect()
    transaction = connection.begin()
    db_session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield db_session
    finally:
        db_session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.mark.parametrize("change", [{"email": "alice2@x.com"}, {"password": "new-pass-22"}])
def test_updating_settings_never_returns_the_password_hash(client, change):
    client.post(REGISTER, json=ALICE)
    client.post(LOGIN, json={"email": ALICE["email"], "password": ALICE["password"]})

    response = client.post(SETTINGS, json=change)

    assert response.status_code == 200
    assert "password_hash" not in response.json()
