"""Explicit, recipient-scoped field allowlists for the downloadable data export."""

import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Block, Friendship, Notification, Profile, Song, Top10Comment,
    Top10Entry, Top10Reaction, User,
)
from app.notifications import MESSAGES

EXPORT_VERSION = 1


def _timestamp(value: datetime.datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def build_user_export(session: Session, user: User) -> dict:
    """Build an in-memory snapshot of this authenticated user's data.

    Keep every query anchored to user.id. Other users' email addresses, profile
    text, comments and inbound blocks are never selected for this export.
    """
    user_id = user.id
    profile = session.scalar(select(Profile).where(Profile.user_id == user_id))
    top10 = session.execute(
        select(Top10Entry, Song)
        .join(Song, Top10Entry.song_id == Song.id)
        .where(Top10Entry.user_id == user_id)
        .order_by(Top10Entry.rank)
    ).all()
    friendships = session.scalars(
        select(Friendship)
        .where(or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id))
        .order_by(Friendship.id)
    ).all()
    blocks = session.scalars(
        select(Block).where(Block.blocker_id == user_id).order_by(Block.blocked_id)
    ).all()
    comments = session.scalars(
        select(Top10Comment).where(Top10Comment.author_id == user_id).order_by(Top10Comment.id)
    ).all()
    reactions = session.scalars(
        select(Top10Reaction).where(Top10Reaction.author_id == user_id).order_by(Top10Reaction.id)
    ).all()
    notifications = session.scalars(
        select(Notification).where(Notification.recipient_id == user_id).order_by(Notification.id)
    ).all()

    return {
        "format_version": EXPORT_VERSION,
        "exported_at": _timestamp(datetime.datetime.now(datetime.timezone.utc)),
        "account": {
            "id": user.id,
            "email": user.email,
            "is_verified": user.is_verified,
            "failed_login_count": user.failed_login_count,
            "locked_until": _timestamp(user.locked_until),
            "deleted_at": _timestamp(user.deleted_at),
            "created_at": _timestamp(user.created_at),
            "updated_at": _timestamp(user.updated_at),
        },
        "profile": None if profile is None else {
            "id": profile.id,
            "display_name": profile.display_name,
            "avatar_url": profile.avatar_url,
            "bio": profile.bio,
            "is_top10_public": profile.is_top10_public,
            "is_online": profile.is_online,
            "last_seen_at": _timestamp(profile.last_seen_at),
            "created_at": _timestamp(profile.created_at),
            "updated_at": _timestamp(profile.updated_at),
        },
        "top10": [
            {
                "id": entry.id,
                "rank": entry.rank,
                "created_at": _timestamp(entry.created_at),
                "updated_at": _timestamp(entry.updated_at),
                "song": {
                    "id": song.id,
                    "provider": song.provider,
                    "provider_id": song.provider_id,
                    "title": song.title,
                    "artist": song.artist,
                    "album": song.album,
                    "cover_url": song.cover_url,
                    "duration_ms": song.duration_ms,
                },
            }
            for entry, song in top10
        ],
        "friendships": [
            {
                "id": row.id,
                "other_user_id": row.addressee_id if row.requester_id == user_id else row.requester_id,
                "direction": "sent" if row.requester_id == user_id else "received",
                "status": row.status,
                "created_at": _timestamp(row.created_at),
                "updated_at": _timestamp(row.updated_at),
            }
            for row in friendships
        ],
        "blocks": [
            {"blocked_user_id": row.blocked_id, "created_at": _timestamp(row.created_at)}
            for row in blocks
        ],
        "authored_comments": [
            {
                "id": row.id,
                "top10_owner_id": row.top10_owner_id,
                "body": row.body,
                "created_at": _timestamp(row.created_at),
                "updated_at": _timestamp(row.updated_at),
            }
            for row in comments
        ],
        "reactions": [
            {
                "id": row.id,
                "top10_owner_id": row.top10_owner_id,
                "reaction": row.reaction,
                "created_at": _timestamp(row.created_at),
                "updated_at": _timestamp(row.updated_at),
            }
            for row in reactions
        ],
        "received_notifications": [
            {
                "id": row.id,
                "event_type": row.event_type,
                "message": MESSAGES.get(row.event_type, "Notification"),
                "created_at": _timestamp(row.created_at),
                "read_at": _timestamp(row.read_at),
            }
            for row in notifications
        ],
    }
