"""WebSocket handshake configuration, read from the backend environment."""

import os
from urllib.parse import urlsplit

LOCAL_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def allowed_websocket_origins() -> frozenset[str]:
    """Exact browser origins; an explicitly empty setting disables connections."""
    origins = frozenset(
        value.strip()
        for value in os.environ.get("WEBSOCKET_ALLOWED_ORIGINS", LOCAL_ORIGINS).split(",")
        if value.strip()
    )
    for origin in origins:
        try:
            parsed = urlsplit(origin)
            port = parsed.port  # Validate malformed/out-of-range ports.
            valid = (
                parsed.scheme in {"http", "https"} and parsed.hostname
                and not parsed.username and not parsed.password
                and not parsed.path and not parsed.query and not parsed.fragment
                and "*" not in origin and not any(c.isspace() for c in origin)
                and (port is None or port > 0)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("WEBSOCKET_ALLOWED_ORIGINS must contain exact HTTP(S) origins")
    return origins
