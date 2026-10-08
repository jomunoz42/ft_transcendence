# TODO: Update HTTPExceptions to match the right error status code
# TODO: Add tests
# TODO: Update current_user_id with Andre's function
# TODO: Add current_user to any current_user-only function (eg. updatetop10)
# TODO: Review class exception

from fastapi import Depends, FastAPI, APIRouter, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.db import get_session

# ROUTES
from app.routes.v1.settings import router as settings
from app.routes.v1.users import router as users
from app.routes.v1.profiles import router as profiles
from app.routes.v1.friendships import router as friendships
from app.routes.v1.top10s import router as top10s

app = FastAPI()
app.include_router(settings,		prefix="/api/v1/settings")
app.include_router(users,			prefix="/api/v1/users")
app.include_router(profiles,		prefix="/api/v1/profiles")
app.include_router(friendships,		prefix="/api/v1/friendships")
app.include_router(top10s,			prefix="/api/v1/top10s")

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
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f">>> ACTIVE CONNECTIONS: {len(self.active_connections)} <<<", flush=True)

    def disconnect(self, websocket: WebSocket):
        if websocket not in self.active_connections:
            return
        self.active_connections.remove(websocket)
        print(f">>> ACTIVE CONNECTIONS: {len(self.active_connections)} <<<", flush=True)

    async def broadcast(self, message: str):
        event = {
            "type": "message",
            "data": {
                "text": message
            }
        }
        for connection in self.active_connections.copy():
            try:
                await connection.send_json(event)
            except WebSocketDisconnect:
                self.disconnect(connection)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            message = await websocket.receive_text()
            await manager.broadcast(message)

    except WebSocketDisconnect:
        print(">>> WEBSOCKET DISCONNECTED <<<", flush=True)
    finally:
        manager.disconnect(websocket)
