"""Bridge synchronous HTTP handlers to the application's realtime event loop."""

import logging
from collections.abc import Callable

from anyio import from_thread
from fastapi import Request

logger = logging.getLogger(__name__)
LogoutNotifier = Callable[[str], None]


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
