"""Database layer — owned by André (auth, database, social features).

The one place the backend builds an engine and hands out sessions. Everything
that needs a session depends on `get_session` rather than creating its own
engine. SQLAlchemy models land in `models.py` alongside this.

This package lives under `backend/` because Alembic and SQLAlchemy have to be
importable by the app, but the database concern is owned here rather than by
the backend as a whole. Usage guide: `docs/andre_docs_code/database.md`.
"""

from app.db.models import Friendship
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from .friendships import are_friends
