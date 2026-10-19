import asyncio
import logging
from enum import Enum, auto

from sqlalchemy.exc import DBAPIError, OperationalError, TimeoutError as PoolTimeout
from fastapi import WebSocket
from app.db.friendships import list_friends
from app.db import SessionLocal
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)
DB_TIMEOUT = 6


class PresenceResult(Enum):
    DELIVERED = auto()
    RETRY = auto()
    FAILED = auto()


def is_transient_failure(error: Exception) -> bool:
    if isinstance(error, (TimeoutError, OSError, PoolTimeout)):
        return True
    if isinstance(error, DBAPIError):
        if error.connection_invalidated:
            return True
        if isinstance(error, OperationalError):
            # psycopg2 connection failures may have no SQLSTATE. Explicit
            # configuration/authentication/schema errors must not loop.
            code = getattr(error.orig, "pgcode", None)
            return code is None or code.startswith("08") or code in {
                "40001", "40P01", "55P03", "57014", "57P01", "57P02", "57P03",
            }
    return False


def find_presence_recipients(user_id: int) -> list[int]:
    with SessionLocal() as session:
        return [friend.id for friend in list_friends(session, user_id)]


async def notify_presence(manager, user_id: int, online: bool) -> None:
    async with asyncio.timeout(DB_TIMEOUT):
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
        if (user_id in manager.active_connections) != online:
            return
        await manager.send_to_user(friend_id, event)


async def notify_presence_safely(manager, user_id: int, online: bool) -> PresenceResult:
    try:
        await notify_presence(manager, user_id, online)
        return PresenceResult.DELIVERED
    except Exception as error:
        logger.exception(
            "Failed to notify presence for user %s (online=%s)",
            user_id,
            online,
        )
        return PresenceResult.RETRY if is_transient_failure(error) else PresenceResult.FAILED


def get_online_friends(manager, friend_ids: list[int]) -> list[int]:
    online_friends = []

    for friend_id in friend_ids:
        if friend_id in manager.active_connections:
            online_friends.append(friend_id)

    return online_friends


async def send_presence_snapshot(manager, websocket: WebSocket, user_id: int) -> bool:
    if websocket not in manager.active_connections.get(user_id, set()):
        return False
    try:
        async with asyncio.timeout(DB_TIMEOUT):
            friend_ids = await run_in_threadpool(find_presence_recipients, user_id)
    except Exception as error:
        if websocket not in manager.initializing and is_transient_failure(error):
            # A refresh can retry on the next tick without discarding a healthy
            # transport. Initial snapshots must still succeed before readiness.
            logger.warning("Presence refresh temporarily unavailable for user %s", user_id)
            return False
        raise

    if (websocket not in manager.initializing
            and manager.friend_ids.get(websocket) == frozenset(friend_ids)):
        return True
    online_friends = get_online_friends(manager, friend_ids)

    event = {
        "type": "presence_snapshot",
        "data": {
            "online_user_ids": online_friends,
        },
    }

    delivered = await manager.send_frame(websocket, user_id, event, snapshot=True)
    if delivered and websocket in manager.active_connections.get(user_id, set()):
        manager.friend_ids[websocket] = frozenset(friend_ids)
    return delivered


async def send_presence_snapshot_safely(manager, websocket: WebSocket, user_id: int) -> bool:
    try:
        return await send_presence_snapshot(manager, websocket, user_id)
    except Exception:
        logger.exception(
            "Failed to send presence snapshot for user %s",
            user_id,
        )
        manager.disconnect(websocket, user_id)
        await manager.close_socket(websocket)
        return False
