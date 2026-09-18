# MyPlaylist — Database Schema Design

Owner: André (auth, database, social features). Status: design drafted, framework and ORM both confirmed.

## Stack

- **Database:** self-managed PostgreSQL.
- **Web framework:** FastAPI — confirmed 2026-09-17 (João's default, Victor agreed).
- **ORM/migrations:** [SQLAlchemy](https://docs.sqlalchemy.org/) + [Alembic](https://alembic.sqlalchemy.org/) — confirmed 2026-09-17, replacing the earlier Prisma Client Python choice. João proposed the switch: Prisma is TypeScript-ecosystem-first, while SQLAlchemy is the standard Python route and gives migrations via Alembic. Decided before any backend code depended on the Prisma schema, so the switch was cheap.

## Scope

Covers milestone 1 (register/login, profile, Top 10, friend request/accept, view friends' Top 10, persistence) plus near-term social features (comments/reactions). Chat/WebSockets is out of scope here (Person 4/João's area).

## Schema (SQLAlchemy 2.0 declarative style)

```python
from __future__ import annotations

import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))  # GDPR soft-delete; NULL = active
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    top10_entries: Mapped[list["Top10Entry"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sent_requests: Mapped[list["Friendship"]] = relationship(
        foreign_keys="Friendship.requester_id", back_populates="requester", cascade="all, delete-orphan"
    )
    received_requests: Mapped[list["Friendship"]] = relationship(
        foreign_keys="Friendship.addressee_id", back_populates="addressee", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Top10Comment"]] = relationship(back_populates="author", cascade="all, delete-orphan")
    reactions: Mapped[list["Top10Reaction"]] = relationship(back_populates="author", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String)
    bio: Mapped[str | None] = mapped_column(String)
    is_top10_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # False = friends only, True = public; enforced in the route layer, not the DB
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # written by WebSocket layer, read elsewhere
    last_seen_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="profile")


class Song(Base):
    __tablename__ = "songs"
    __table_args__ = (UniqueConstraint("provider", "provider_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "spotify", "deezer", "manual"
    provider_id: Mapped[str] = mapped_column(String, nullable=False)  # external track id, or generated id for manual entries
    title: Mapped[str] = mapped_column(String, nullable=False)
    artist: Mapped[str] = mapped_column(String, nullable=False)
    album: Mapped[str | None] = mapped_column(String)
    cover_url: Mapped[str | None] = mapped_column(String)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)  # provider-specific extras
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    top10_entries: Mapped[list["Top10Entry"]] = relationship(back_populates="song")


class Top10Entry(Base):
    __tablename__ = "top10_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "rank"),
        UniqueConstraint("user_id", "song_id"),
        CheckConstraint("rank BETWEEN 1 AND 10", name="ck_top10_entries_rank_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    song_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("songs.id", ondelete="RESTRICT"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-10, enforced by the CHECK constraint above
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="top10_entries")
    song: Mapped["Song"] = relationship(back_populates="top10_entries")


class Friendship(Base):
    __tablename__ = "friendships"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    requester_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    addressee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)  # pending | accepted | declined | blocked
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    requester: Mapped["User"] = relationship(foreign_keys=[requester_id], back_populates="sent_requests")
    addressee: Mapped["User"] = relationship(foreign_keys=[addressee_id], back_populates="received_requests")


# One row per unordered pair. Unlike Prisma, SQLAlchemy can express the LEAST/GREATEST
# functional unique index directly — no raw-SQL migration needed.
Index(
    "ux_friendships_unordered_pair",
    func.least(Friendship.requester_id, Friendship.addressee_id),
    func.greatest(Friendship.requester_id, Friendship.addressee_id),
    unique=True,
)


class Top10Comment(Base):
    __tablename__ = "top10_comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    top10_owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )  # FK added 2026-09-18: without it, deleting a user orphans every comment left on their Top 10
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    author: Mapped["User"] = relationship(back_populates="comments")


class Top10Reaction(Base):
    __tablename__ = "top10_reactions"
    __table_args__ = (UniqueConstraint("top10_owner_id", "author_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    top10_owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reaction: Mapped[str] = mapped_column(String, nullable=False)  # like | dislike
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    author: Mapped["User"] = relationship(back_populates="reactions")
```

Notes:
- `Top10Entry` has no separate "list header" table — each user has exactly one Top 10, so `(user_id, rank)` uniqueness is the whole model. Reordering updates `rank` on affected rows in one transaction.
- `Friendship` uses one row per unordered pair (not two directional rows), enforced by the functional unique index above — a native SQLAlchemy `Index`, not a raw-SQL migration like Prisma needed.
- `CHECK (rank BETWEEN 1 AND 10)` is a native `CheckConstraint` on `Top10Entry` — also no raw SQL needed, unlike the Prisma version.
- `Profile.is_top10_public` is the V1 privacy setting (added 2026-09-18, confirmed against `docs/myplaylist_simulator.py`, which shows exactly two states: public / friends-only). Visibility depends on *who is viewing*, so no DB constraint can enforce it — the column stores the flag, the route layer reads it. Boolean rather than a string enum because there are only two states; widen later if a third appears.
- `Top10Comment.top10_owner_id` and `Top10Reaction.top10_owner_id` carry an FK to `users.id` with `ON DELETE CASCADE` (added 2026-09-18). They were FK-less only because the original Prisma model was; that rationale died with the Prisma switch. Without the FK, deleting a user cascades the rows they *wrote* but orphans every row written *on their Top 10*.

## Alembic setup

```bash
pip install sqlalchemy alembic psycopg2-binary
alembic init alembic
```

- In `alembic.ini`, set `sqlalchemy.url` to the Postgres connection string (or leave blank and set it from `env.py` via an environment variable — don't commit real credentials).
- In `alembic/env.py`, import `Base` from the models module above and set `target_metadata = Base.metadata`.
- Generate and apply the initial migration:

```bash
alembic revision --autogenerate -m "init schema"
alembic upgrade head
```

## Placeholders (safe to start with, cheap to change later)

- **PK style:** bigint autoincrement. Switch to a UUID primary key later if IDs need to be public-facing — no cost until real data exists. (Note André - Should we do with unsigned?)
- **`songs.provider_id` for manual entries:** use `provider = "manual"`, `provider_id = <generated uuid>`. Confirm with João when the Song service is built.
- **GDPR erasure:** default to cascade-delete on comments/reactions when a user is deleted. Revisit when the GDPR module is actually scoped.

## Next step

Scaffold `backend/` with FastAPI, wire up the SQLAlchemy engine/session, and run `alembic upgrade head` against a local Postgres container. No decisions block this — deferred per André's plan-only status until his BPI/EY calendar load eases.
