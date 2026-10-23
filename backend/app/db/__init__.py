"""Database layer — owned by André (auth, database, social features).

The one place the backend builds an engine and hands out sessions. Everything
that needs a session depends on `get_session` rather than creating its own
engine. SQLAlchemy models land in `models.py` alongside this.

This package lives under `backend/` because Alembic and SQLAlchemy have to be
importable by the app, but the database concern is owned here rather than by
the backend as a whole. Usage guide: `docs/andre_docs_code/database.md`.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from .models import User

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def get_session():
    """FastAPI dependency: one session per request, always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def get_current_user():
    user_id = os.environ["CURRENT_USERID"]
    session = SessionLocal()
    user = session.query(User).filter(User.id == user_id).first()
    try:
        yield user
    finally:
        session.close()
