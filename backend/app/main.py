# TODO: Update HTTPExceptions to match the right error status code
# TODO: Add tests
# TODO: Update current_user_id with Andre's function
# TODO: Add current_user to any current_user-only function (eg. updatetop10)
# TODO: Review class exception

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, APIRouter, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.websocket import authenticate_websocket
from starlette.concurrency import run_in_threadpool
from app.db import get_session
from app.realtime.config import allowed_websocket_origins
from app.realtime.manager import ConnectionManager
from app.realtime.presence import DB_TIMEOUT

ALLOWED_WEBSOCKET_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}

@asynccontextmanager
async def lifespan(app):
    manager.start()
    try:
        yield
    finally:
        await manager.stop()

logger = logging.getLogger(__name__)
app = FastAPI(lifespan=lifespan)

ALLOWED_WEBSOCKET_ORIGINS = allowed_websocket_origins()

# ROUTES
from app.routes.v1.auth import router as auth
app.include_router(auth, prefix="/api/v1/auth")
from app.routes.v1.settings import router as settings
app.include_router(settings, prefix="/api/v1/settings")
from app.routes.v1.profiles import router as profiles
app.include_router(profiles, prefix="/api/v1/profiles")

@app.get("/health")
def health(response: Response, session: Session = Depends(get_session)):
    """Report whether the backend can actually reach the database.

    A static 200 would make this endpoint useless as a readiness check, so the
    database is queried on every call.
    """
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "database": "unreachable"}
    return {"status": "ok", "database": "ok"}


manager = ConnectionManager()
app.state.realtime_manager = manager


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    origin = websocket.headers.get("origin")

    if origin not in ALLOWED_WEBSOCKET_ORIGINS:
        await manager.close_socket(websocket, code=1008)
        return
    
    token = websocket.cookies.get(SESSION_COOKIE_NAME)

    if not token:
        await manager.close_socket(websocket, code=1008)
        return

    try:
        async with asyncio.timeout(DB_TIMEOUT):
            user_id = await run_in_threadpool(authenticate_websocket, token)
    except (SQLAlchemyError, TimeoutError):
        logger.error("WebSocket authentication database unavailable")
        await manager.close_socket(websocket)
        return

    if user_id is None:
        await manager.close_socket(websocket, code=1008)
        return

    receive_task = disconnected_task = None
    try:
        await manager.connect(websocket, user_id)
        manager.session_tokens[websocket] = token
        if not await manager.initialize(websocket, user_id):
            return

        disconnected = manager.disconnected.get(websocket)
        if disconnected is None:
            return
        disconnected_task = asyncio.create_task(disconnected.wait())
        loop = asyncio.get_running_loop()
        next_session_check = loop.time() + manager.SESSION_REVALIDATE_INTERVAL
        next_friendship_refresh = loop.time() + manager.FRIENDSHIP_REFRESH_INTERVAL
        while websocket in manager.active_connections.get(user_id, set()):
            # Independent deadlines; incoming traffic cannot postpone either.
            if loop.time() >= next_session_check:
                if not await manager.revalidate(websocket, user_id):
                    return
                next_session_check = loop.time() + manager.SESSION_REVALIDATE_INTERVAL
            if loop.time() >= next_friendship_refresh:
                manager.schedule_snapshot(websocket, user_id)
                next_friendship_refresh = loop.time() + manager.FRIENDSHIP_REFRESH_INTERVAL
            if receive_task is None:
                receive_task = asyncio.create_task(websocket.receive())
            deadline = min(next_session_check, next_friendship_refresh)
            done, _ = await asyncio.wait(
                (receive_task, disconnected_task),
                timeout=max(0, deadline - loop.time()),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if disconnected_task in done:
                break
            if receive_task in done:
                message = receive_task.result()
                receive_task = None
                if message["type"] == "websocket.disconnect":
                    break
            # Presence is server-driven; there are no client commands yet.

    except WebSocketDisconnect:
        pass

    finally:
        manager.disconnect(websocket, user_id)
        tasks = [task for task in (receive_task, disconnected_task) if task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
