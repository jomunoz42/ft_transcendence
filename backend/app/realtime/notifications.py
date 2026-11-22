"""Bridge synchronous HTTP handlers to the application's realtime event loop."""

import logging
from collections.abc import Callable

from anyio import from_thread
from fastapi import Request
from app.crud.notification import NotificationEvents

logger = logging.getLogger(__name__)
LogoutNotifier = Callable[[str], None]
FriendsNotifier = Callable[..., None]
NotificationsNotifier = Callable[[NotificationEvents], None]


def get_notifications_notifier(request: Request) -> NotificationsNotifier:
    """Deliver newly persisted IDs after commit; REST remains the durable fallback.

No message, actor, source content or internal event key crosses this bridge.
The existing manager handles every local session, send locks and revalidation.
"""
    def notify(events: NotificationEvents) -> None:
        for recipient_id, notification_id in events:
            try:
                from_thread.run(
                    request.app.state.realtime_manager.send_to_user,
                    recipient_id, {"type": "notification", "data": {"id": notification_id}},
                )
            except Exception:
                logger.error("Realtime notification delivery failed; notification remains available through REST")

    return notify


def get_logout_notifier(request: Request) -> LogoutNotifier:
    def notify(token: str) -> None:
        try:
            # FastAPI runs synchronous routes in AnyIO worker threads. Wait for
            # cleanup on their originating event loop, never mutate it here.
            from_thread.run(request.app.state.realtime_manager.disconnect_session, token)
        except Exception:
            # The database commit has already revoked the session. Preserve the
            # HTTP logout result; periodic/outbound checks provide the fallback.
            # Do not log exception details, which could contain the cookie.
            logger.error("Realtime logout notification failed; session checks remain active")

    return notify


def get_friends_notifier(request: Request) -> FriendsNotifier:
    """Return notify(*user_ids): after a committed friendship change, refresh the presence snapshot on every socket of those users. Never raises."""
    manager = request.app.state.realtime_manager

    def refresh(user_ids: tuple[int, ...]) -> None:
        for user_id in user_ids:
            for socket in manager.active_connections.get(user_id, set()).copy():
                manager.schedule_snapshot(socket, user_id)

    def notify(*user_ids: int) -> None:
        try:
            from_thread.run_sync(refresh, user_ids)
        except Exception:
            logger.error("Realtime friendship notification failed; periodic refresh remains active")

    return notify
