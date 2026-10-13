from fastapi import Depends, FastAPI, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.websocket import authenticate_websocket
from app.db import get_session
from app.realtime.presence import notify_presence_safely
from app.realtime.presence import (notify_presence_safely, send_presence_snapshot_safely)


app = FastAPI()

ALLOWED_WEBSOCKET_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}

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


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int) -> bool:
        await websocket.accept()

        was_offline = user_id not in self.active_connections

        if was_offline:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)

        print(f">>> ACTIVE CONNECTIONS: {len(self.active_connections)} <<<", flush=True)
        return was_offline


    def disconnect(self, websocket: WebSocket, user_id: int) -> bool:
        if user_id not in self.active_connections:
            return False

        connections = self.active_connections[user_id]

        if websocket not in connections:
            return False

        connections.discard(websocket)

        if not connections:
            del self.active_connections[user_id]
            print(f">>> ACTIVE CONNECTIONS: {len(self.active_connections)} <<<", flush=True)
            return True

        print(f">>> ACTIVE CONNECTIONS: {len(self.active_connections)} <<<", flush=True)
        return False


    async def broadcast(self, message: str):
        event = {"type": "message", "data": {"text": message}}

        for user_id, connections in list(self.active_connections.items()):
            for connection in connections.copy():
                try:
                    await connection.send_json(event)
                except (WebSocketDisconnect, OSError):
                    became_offline = self.disconnect(connection, user_id)

                    if became_offline:
                        await notify_presence_safely(self, user_id, False)


    async def send_to_user(self, user_id: int, event: dict):
        connections = self.active_connections.get(user_id)

        if not connections:
            return

        for connection in connections.copy():
            try:
                await connection.send_json(event)
            except (WebSocketDisconnect, OSError):
                became_offline = self.disconnect(connection, user_id)

                if became_offline:
                    await notify_presence_safely(self, user_id, False)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    origin = websocket.headers.get("origin")

    if origin not in ALLOWED_WEBSOCKET_ORIGINS:
        await websocket.close(code=1008)
        return
    
    token = websocket.cookies.get(SESSION_COOKIE_NAME)

    if not token:
        await websocket.close(code=1008)
        return

    user_id = await run_in_threadpool(authenticate_websocket, token)

    if user_id is None:
        await websocket.close(code=1008)
        return

    became_online = await manager.connect(websocket, user_id)

    try:
        await send_presence_snapshot_safely(manager, websocket, user_id)

        if websocket not in manager.active_connections.get(user_id, set()):
            return

        if became_online:
            await notify_presence_safely(manager, user_id, True)

        while True:
            message = await websocket.receive_text()
            await manager.broadcast(message)

    except WebSocketDisconnect:
        print(">>> WEBSOCKET DISCONNECTED <<<", flush=True)

    finally:
        became_offline = manager.disconnect(websocket, user_id)

        if became_offline:
            await notify_presence_safely(manager, user_id, False)
