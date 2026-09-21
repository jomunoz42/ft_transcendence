"""SQLAlchemy models — the schema designed in `database/db-schema.md`.

Alembic autogenerates migrations by comparing these definitions against the live
database, so every model must be reachable from this module's imports.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
    comments: Mapped[list["Top10Comment"]] = relationship(
        foreign_keys="Top10Comment.author_id", back_populates="author", cascade="all, delete-orphan"
    )
    reactions: Mapped[list["Top10Reaction"]] = relationship(
        foreign_keys="Top10Reaction.author_id", back_populates="author", cascade="all, delete-orphan"
    )


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String)
    bio: Mapped[str | None] = mapped_column(String)
    is_top10_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # False = friends only; enforced in the route layer, not the DB
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # written by the WebSocket layer, read elsewhere
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
    __table_args__ = (
        CheckConstraint("requester_id <> addressee_id", name="ck_friendships_not_self"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'blocked')", name="ck_friendships_status"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    requester_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    addressee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)  # allowed values enforced by ck_friendships_status
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    requester: Mapped["User"] = relationship(foreign_keys=[requester_id], back_populates="sent_requests")
    addressee: Mapped["User"] = relationship(foreign_keys=[addressee_id], back_populates="received_requests")


# One row per unordered pair: A->B and B->A both map to (least, greatest), so the
# second request collides with the first whichever direction it comes from.
Index(
    "ux_friendships_unordered_pair",
    func.least(Friendship.requester_id, Friendship.addressee_id),
    func.greatest(Friendship.requester_id, Friendship.addressee_id),
    unique=True,
)


class Top10Comment(Base):
    __tablename__ = "top10_comments"
    __table_args__ = (
        CheckConstraint("length(trim(body)) > 0", name="ck_top10_comments_body_not_blank"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    top10_owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # whose Top 10
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # who wrote it
    body: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    author: Mapped["User"] = relationship(foreign_keys=[author_id], back_populates="comments")


class Top10Reaction(Base):
    __tablename__ = "top10_reactions"
    __table_args__ = (
        UniqueConstraint("top10_owner_id", "author_id"),
        CheckConstraint("reaction IN ('like', 'dislike')", name="ck_top10_reactions_value"),
        CheckConstraint("author_id <> top10_owner_id", name="ck_top10_reactions_not_own"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    top10_owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # whose Top 10
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # who reacted
    reaction: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    author: Mapped["User"] = relationship(foreign_keys=[author_id], back_populates="reactions")
