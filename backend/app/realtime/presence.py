from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Friendship
from app.db import SessionLocal
from starlette.concurrency import run_in_threadpool
import logging

logger = logging.getLogger(__name__)


def get_presence_recipients(session: Session, user_id: int) -> list[int]:
    friendships = session.scalars(
        select(Friendship).where(
            Friendship.status == "accepted",
            or_(
                Friendship.requester_id == user_id,
                Friendship.addressee_id == user_id,
            ),
        )
    )

    recipients = []

    for friendship in friendships:
        if friendship.requester_id == user_id:
            recipients.append(friendship.addressee_id)
        else:
            recipients.append(friendship.requester_id)

    return recipients


def find_presence_recipients(user_id: int) -> list[int]:
    with SessionLocal() as session:
        return get_presence_recipients(session, user_id)


async def notify_presence(manager, user_id: int, online: bool) -> None:
    friend_ids = await run_in_threadpool(find_presence_recipients, user_id)

    if (user_id in manager.active_connections) != online:
        return
    
    event = {
        "type": "presence",
        "data": {
            "user_id": user_id,
            "online": online,
        },
    }

    for friend_id in friend_ids:
        await manager.send_to_user(friend_id, event)


async def notify_presence_safely(manager, user_id: int, online: bool) -> None:
    try:
        await notify_presence(manager, user_id, online)
    except Exception:
        logger.exception(
            "Failed to notify presence for user %s (online=%s)",
            user_id,
            online,
        )