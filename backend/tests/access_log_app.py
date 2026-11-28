"""Minimal ASGI probe for real-process Uvicorn logging tests."""

from urllib.parse import parse_qs

from app.access_logging import install_query_free_uvicorn_logging

install_query_free_uvicorn_logging()


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    query = parse_qs(scope["query_string"].decode())
    if scope["type"] == "websocket":
        # The query must still reach the app; Uvicorn's log filter only changes
        # the copy in its log record.
        if query.get("token") != ["synthetic-ws-token"]:
            await send({"type": "websocket.close", "code": 1008})
            return
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.close", "code": 1000})
        return

    path = scope["path"]
    if path.endswith("/callback"):
        status = 200 if query.get("code") == ["synthetic/code+value"] and query.get("state") == ["synthetic state&value"] else 400
    elif path == "/raise":
        raise RuntimeError("synthetic handler failure")
    elif scope["method"] == "POST":
        status = 201
    else:
        status = 200
    body = b"rejected" if status >= 400 else b"accepted"
    await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": body})
