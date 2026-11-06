"""The one place the backend builds an engine and hands out sessions.

Usage guide: `docs/andre_docs_code/database.md`.
"""

import os

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import User, Profile

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

# ##############################
# serializers
# ##############################

def _me(user: User) -> dict:
    """The user fields the API may show; never the password hash."""
    return {"email": user.email, "is_verified": user.is_verified, "created_at": user.created_at, "updated_at": user.updated_at, "deleted_at": user.deleted_at}

def _me_profile(profile: Profile) -> dict:
    """The user fields the API may show; never the password hash."""
    return {"id": profile.id, "display_name": profile.display_name, "avatar_url": profile.avatar_url, "bio": profile.bio, "is_top10_public": profile.is_top10_public, "is_online": profile.is_online}

def _public(user: User) -> dict:
    """The user fields the API may show; never the password hash."""
    return {"id": user.id, "email": user.email, "display_name": user.profile.display_name}
