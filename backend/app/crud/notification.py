"""Persistent notifications. All changes belong to the caller's transaction.

Producers must supply a stable, recipient-scoped event key identifying one
logical event (including its kind and source operation ID). Reuse it on retry;
use a new key for a genuinely new event, even if the message is identical.
Messages must be recipient-safe summaries, not secrets or private source data.
"""

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import errors
from app.db.models import Notification

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_OFFSET = 10_000
NotificationEvents = list[tuple[int, int]]  # (recipient ID, newly inserted notification ID)


def create_notification(
    session: Session, recipient_id: int, *, event_key: str,
    event_type: str, message: str, actor_id: int | None = None,
    events: NotificationEvents | None = None,
) -> Notification:
    """Create once per recipient/event key, including concurrent retries. Never commits.

The first payload wins. Retries return that row without changing its content
or read status. The key is internal and must not be derived from message text.
"""
    if not event_key.strip() or len(event_key) > 255:
        raise ValueError("event_key must contain 1 to 255 characters")
    session.flush()
    notification = session.scalar(
        insert(Notification)
        .values(recipient_id=recipient_id, actor_id=actor_id, event_key=event_key,
                event_type=event_type, message=message)
        .on_conflict_do_nothing(constraint="uq_notifications_recipient_event_key")
        .returning(Notification)
    )
    if notification is not None:
        if events is not None:
            events.append((recipient_id, notification.id))
        return notification
    return session.scalars(select(Notification).where(
        Notification.recipient_id == recipient_id, Notification.event_key == event_key,
    )).one()


def list_notifications(
    session: Session, recipient_id: int, *, limit: int = DEFAULT_LIMIT, offset: int = 0,
) -> list[Notification]:
    """List only this recipient's notifications, with deterministic newest-first ordering."""
    if not 1 <= limit <= MAX_LIMIT or not 0 <= offset <= MAX_OFFSET:
        raise ValueError("notification pagination is out of bounds")
    return list(session.scalars(
        select(Notification).where(Notification.recipient_id == recipient_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit).offset(offset)
    ))


def unread_count(session: Session, recipient_id: int) -> int:
    return session.scalar(select(func.count()).select_from(Notification).where(
        Notification.recipient_id == recipient_id, Notification.read_at.is_(None),
    ))


def mark_as_read(session: Session, recipient_id: int, notification_id: int) -> Notification:
    """Mark an owned notification once; missing and foreign IDs both return 404. Never commits."""
    owned = (Notification.id == notification_id, Notification.recipient_id == recipient_id)
    notification = session.scalar(
        update(Notification).where(*owned, Notification.read_at.is_(None))
        .values(read_at=func.now()).returning(Notification)
        .execution_options(populate_existing=True)
    )
    if notification is None:
        notification = session.scalar(select(Notification).where(*owned).execution_options(populate_existing=True))
    if notification is None:
        raise errors.HTTP_404_NOT_FOUND
    return notification
