"""Keep request query strings out of Uvicorn's HTTP and WebSocket logs.

Uvicorn formats access records from the ASGI scope. Filtering the log record
leaves the scope and its query string available to the application unchanged.
"""

import logging


class QueryFreeUvicornFilter(logging.Filter):
    """Remove the entire query string from Uvicorn's request path argument."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "uvicorn.access":
            # If a Uvicorn upgrade changes its record layout, do not emit an
            # unexamined request line that could contain a new secret shape.
            if not isinstance(record.args, tuple) or len(record.args) != 5 or not isinstance(record.args[2], str):
                return False
            path_index = 2
        elif (
            record.name == "uvicorn.error"
            and isinstance(record.msg, str)
            and '"WebSocket %s"' in record.msg
            and isinstance(record.args, tuple)
            and len(record.args) >= 2
        ):
            path_index = 1
        else:
            return True

        path = record.args[path_index]
        if isinstance(path, str) and "?" in path:
            args = list(record.args)
            args[path_index] = path.split("?", 1)[0]
            record.args = tuple(args)
        return True


def install_query_free_uvicorn_logging() -> None:
    """Install once per worker, after Uvicorn configures its loggers."""
    for name in ("uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, QueryFreeUvicornFilter) for item in logger.filters):
            logger.addFilter(QueryFreeUvicornFilter())
