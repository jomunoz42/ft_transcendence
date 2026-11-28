"""SQLAlchemy models — the database schema; usage guide in `docs/andre_docs_code/database.md`.

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
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String)  # NULL = OAuth-only account
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    locked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))  # legacy soft-delete marker; confirmed deletion removes the row
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
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    received_notifications: Mapped[list["Notification"]] = relationship(
        foreign_keys="Notification.recipient_id", back_populates="recipient", cascade="all, delete-orphan"
    )


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str] = mapped_column(String, server_default=text("'/api/v1/avatars/default'"), nullable=False)  # the default until an upload, then /api/v1/avatars/{user_id}?v=...
    bio: Mapped[str | None] = mapped_column(String)
    is_top10_public: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)  # False = friends only; enforced in the route layer, not the DB
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)  # written by the WebSocket layer, read elsewhere
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
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, server_default=text("'{}'"), nullable=False)  # provider-specific extras
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    top10_entries: Mapped[list["Top10Entry"]] = relationship(back_populates="song")


class Top10Entry(Base):
    __tablename__ = "top10_entries"
    __table_args__ = (
        # Deferrable so it is checked per statement, not per row: one UPDATE can swap two ranks.
        UniqueConstraint("user_id", "rank", name="top10_entries_user_id_rank_key", deferrable=True, initially="IMMEDIATE"),
        UniqueConstraint("user_id", "song_id"),
        CheckConstraint("rank BETWEEN 1 AND 10", name="ck_top10_entries_rank_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    song_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("songs.id", ondelete="RESTRICT"), nullable=False, index=True)
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
            "status IN ('pending', 'accepted', 'declined')", name="ck_friendships_status"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    requester_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    addressee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, default="pending", server_default=text("'pending'"), nullable=False)  # allowed values enforced by ck_friendships_status
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


class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (CheckConstraint("blocker_id <> blocked_id", name="ck_blocks_not_self"),)

    blocker_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True,)
    blocked_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OAuthAccount(Base):
    """Links one provider account (e.g. a 42 user) to one local user."""

    __tablename__ = "oauth_accounts"

    provider: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "42"
    provider_id: Mapped[str] = mapped_column(String, primary_key=True)  # the provider's own user id
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship()


class Top10Comment(Base):
    __tablename__ = "top10_comments"
    __table_args__ = (
        CheckConstraint("length(trim(body)) > 0", name="ck_top10_comments_body_not_blank"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    top10_owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)  # whose Top 10
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)  # who wrote it
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
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)  # who reacted
    reaction: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    author: Mapped["User"] = relationship(foreign_keys=[author_id], back_populates="reactions")


class Message(Base):
    """A private chat message; deleting the sender or the recipient deletes it. Soft-deleted users keep their rows until the GDPR purge, so reads must filter deleted_at."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("body ~ '[^[:space:]]'", name="ck_messages_body_not_blank"),
        CheckConstraint("sender_id <> recipient_id", name="ck_messages_not_self"),
        Index("ix_messages_sender_id_recipient_id_created_at_id", "sender_id", "recipient_id", "created_at", "id"),
        Index("ix_messages_recipient_id", "recipient_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recipient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])
    recipient: Mapped["User"] = relationship(foreign_keys=[recipient_id])


class Avatar(Base):
    """A user's uploaded avatar, already re-encoded to a 256x256 WebP; at most one per user."""

    __tablename__ = "avatars"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserSession(Base):
    # Named UserSession so it does not clash with SQLAlchemy's own Session.
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # SHA-256 of the cookie token; the raw token is never stored
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="sessions")


class DeletionRequest(Base):
    """Latest emailed deletion challenge and its per-user rate-limit timestamp."""

    __tablename__ = "privacy_deletion_requests"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_recipient_id_created_at", "recipient_id", "created_at"),
        UniqueConstraint("recipient_id", "event_key", name="uq_notifications_recipient_event_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recipient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    # Required for recipient-scoped event deduplication.
    event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    recipient: Mapped["User"] = relationship(foreign_keys=[recipient_id], back_populates="received_notifications")
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_id])
