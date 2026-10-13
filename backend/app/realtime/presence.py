from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from fastapi import WebSocket
from app.db.models import Friendship
from app.db import SessionLocal
from starlette.concurrency import run_in_threadpool
from fastapi import WebSocket, WebSocketDisconnect
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


def get_online_friends(manager, friend_ids: list[int]) -> list[int]:
    online_friends = []

    for friend_id in friend_ids:
        if friend_id in manager.active_connections:
            online_friends.append(friend_id)

    return online_friends


async def send_presence_snapshot(manager, websocket: WebSocket, user_id: int) -> None:
    friend_ids = await run_in_threadpool(find_presence_recipients, user_id)

    online_friends = get_online_friends(manager, friend_ids)

    event = {
        "type": "presence_snapshot",
        "data": {
            "online_user_ids": online_friends,
        },
    }

    try:
        await websocket.send_json(event)
    except (WebSocketDisconnect, OSError):
        became_offline = manager.disconnect(websocket, user_id)

        if became_offline:
            await notify_presence_safely(manager, user_id, False)

        raise


async def send_presence_snapshot_safely(manager, websocket: WebSocket, user_id: int) -> None:
    try:
        await send_presence_snapshot(manager, websocket, user_id)
    except Exception:
        logger.exception(
            "Failed to send presence snapshot for user %s",
            user_id,
        )