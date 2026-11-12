"""Bridge synchronous HTTP handlers to the application's realtime event loop."""

import logging
from collections.abc import Callable

from anyio import from_thread
from fastapi import Request

logger = logging.getLogger(__name__)
LogoutNotifier = Callable[[str], None]
FriendsNotifier = Callable[..., None]


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
