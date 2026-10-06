from fastapi import Depends, FastAPI, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_session

app = FastAPI()


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
        self.active_connections.remove(websocket)
        print(f">>> ACTIVE CONNECTIONS: {len(self.active_connections)} <<<", flush=True)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_json({
                "type": "message",
                "data": {
                    "text": message
                }
            })


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            message = await websocket.receive_text()
            await manager.broadcast(message)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(">>> WEBSOCKET DISCONNECTED <<<", flush=True)
