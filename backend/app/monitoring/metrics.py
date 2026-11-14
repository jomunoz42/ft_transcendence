from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "myplaylist_http_requests_total",
    "Total number of HTTP requests",
    ["method", "route", "status"],
)

HTTP_DURATION = Histogram(
    "myplaylist_http_request_duration_seconds",
    "Duration of HTTP requests in seconds",
    ["method", "route"],
)

WS_ACTIVE_CONNECTIONS = Gauge(
    "myplaylist_ws_active_connections",
    "Current number of active WebSocket connections",
)

WS_CONNECTIONS_TOTAL = Counter(
    "myplaylist_ws_connections_total",
    "Total number of accepted WebSocket connections",
)

WS_DISCONNECTIONS_TOTAL = Counter(
    "myplaylist_ws_disconnections_total",
    "Total number of removed WebSocket connections",
)