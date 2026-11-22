"""Persist action notifications; HTTP handlers deliver collected IDs after commit."""

import datetime

from sqlalchemy.orm import Session

from app.crud.friendship import are_friends, is_blocked
from app.crud.notification import NotificationEvents, create_notification
from app.db.models import User

MESSAGES = {
    "friend_request.created": "You received a friend request.",
    "friend_request.accepted": "Your friend request was accepted.",
    "friend_request.declined": "Your friend request was declined.",
    "friend_request.cancelled": "A friend request was cancelled.",
    "friendship.removed": "A friendship ended.",
    "comment.created": "Someone commented on your Top 10.",
    "comment.updated": "A comment on your Top 10 was updated.",
    "comment.deleted": "A comment on your Top 10 was deleted.",
    "reaction.created": "Someone reacted to your Top 10.",
    "reaction.updated": "A reaction on your Top 10 was updated.",
    "reaction.deleted": "A reaction on your Top 10 was deleted.",
}


def advance_updated_at(row) -> None:
    """Give each real change a persisted revision, even within one transaction.

Call with the source row locked. PostgreSQL now() is constant for a transaction;
using a strictly increasing updated_at distinguishes A->B->A edits and reopened
requests without adding another version column or hashing private content.
"""
    row.updated_at = max(
        datetime.datetime.now(datetime.timezone.utc),
        row.updated_at + datetime.timedelta(microseconds=1),
    )


def record_action(
    session: Session, source, event_type: str, recipient_id: int, actor_id: int,
    events: NotificationEvents | None = None,
) -> None:
    if recipient_id == actor_id or is_blocked(session, recipient_id, actor_id):
        return
    recipient = session.get(User, recipient_id)
    if recipient is None or recipient.deleted_at is not None:
        return
    if event_type.startswith(("comment.", "reaction.")) and not are_friends(session, recipient_id, actor_id):
        return
    create_notification(
        session, recipient_id, actor_id=actor_id, event_type=event_type,
        message=MESSAGES[event_type],
        event_key=f"{source.__tablename__}:{source.id}:{event_type}:{source.updated_at.astimezone(datetime.timezone.utc).isoformat()}",
        events=events,
    )
