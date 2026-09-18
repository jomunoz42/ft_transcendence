"""Test harness for the database layer.

Tests run against the real Postgres container — the spec rules out mocking the
database, since the constraints being verified are enforced by Postgres itself
and a mock would happily accept what the real database rejects.

Each test runs inside a transaction that is rolled back afterwards, so tests see
a clean database without the schema being rebuilt between them.
"""

import pytest
from sqlalchemy.orm import Session

from app.db import engine


@pytest.fixture
def session():
    connection = engine.connect()
    transaction = connection.begin()
    db_session = Session(bind=connection)
    try:
        yield db_session
    finally:
        db_session.close()
        transaction.rollback()
        connection.close()
