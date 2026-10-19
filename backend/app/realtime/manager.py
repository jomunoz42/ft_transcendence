"""Process-local connections and serialized presence delivery."""

import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.auth.websocket import authenticate_websocket

from app.realtime.presence import (
    DB_TIMEOUT, PresenceResult, notify_presence_safely, send_presence_snapshot_safely,
)

logger = logging.getLogger(__name__)


class ConnectionManager:
    SESSION_REVALIDATE_INTERVAL = 10
    FRIENDSHIP_REFRESH_INTERVAL = 5
    SEND_TIMEOUT = 5
    CLOSE_TIMEOUT = 1
    INITIALIZE_TIMEOUT = 20
    RETRY_INTERVAL = 1
    MAX_RETRY_INTERVAL = 30
    FRESH_JOBS_PER_RETRY = 8
    MAX_INITIALIZATIONS = 64
    MAX_INITIALIZATIONS_PER_USER = 4

    def __init__(self):
        self.active_connections: dict[int, set[WebSocket]] = {}
        self.initializing: set[WebSocket] = set()
        self.session_tokens: dict[WebSocket, str] = {}
        self.friend_ids: dict[WebSocket, frozenset[int]] = {}
        self.snapshot_pending: dict[WebSocket, asyncio.Future] = {}
        # Includes accepts in flight; released on readiness or any failure.
        self.initialization_admissions: dict[WebSocket, int] = {}
        self.send_locks: dict[WebSocket, asyncio.Lock] = {}
        self.disconnected: dict[WebSocket, asyncio.Event] = {}
        # Integers request a current-state update; tuples request a snapshot.
        self.presence_queue: asyncio.Queue = asyncio.Queue()
        self.pending_presence: set[int] = set()
        # user -> (previous delay, next attempt time). Retain offline updates
        # through transient outages, without adding a retry task per user.
        self.retry_presence: dict[int, tuple[float, float]] = {}
        self.presence_worker: asyncio.Task | None = None
        self.stopping = False

    def start(self):
        if self.presence_worker is None or self.presence_worker.done():
            self.stopping = False
            self.presence_worker = asyncio.create_task(self.process_presence_queue())

    async def stop(self):
        self.stopping = True
        if self.presence_worker is not None:
            self.presence_worker.cancel()
            await asyncio.gather(self.presence_worker, return_exceptions=True)
            self.presence_worker = None
        while not self.presence_queue.empty():
            job = self.presence_queue.get_nowait()
            if isinstance(job, tuple) and not job[2].done():
                job[2].set_result(False)
            self.presence_queue.task_done()
        sockets = [socket for sockets in self.active_connections.values() for socket in sockets]
        self.active_connections.clear()
        self.initializing.clear()
        self.session_tokens.clear()
        self.friend_ids.clear()
        self.snapshot_pending.clear()
        self.initialization_admissions.clear()
        self.send_locks.clear()
        for disconnected in self.disconnected.values():
            disconnected.set()
        self.disconnected.clear()
        self.pending_presence.clear()
        self.retry_presence.clear()
        await asyncio.gather(*(self.close_socket(socket) for socket in sockets))
        # Queue/locks must not retain a previous lifespan's event loop.
        self.presence_queue = asyncio.Queue()

    def schedule_presence(self, user_id: int):
        if not self.stopping and user_id not in self.pending_presence:
            self.pending_presence.add(user_id)
            self.presence_queue.put_nowait(user_id)

    async def process_presence_queue(self):
        fresh_jobs = 0
        while True:
            now = asyncio.get_running_loop().time()
            retries = [
                (due, user_id) for user_id, (_, due) in self.retry_presence.items()
                if user_id not in self.pending_presence
            ]
            next_retry, user_id = min(retries, default=(float("inf"), None))
            if next_retry <= now:
                if self.presence_queue.empty() or fresh_jobs >= self.FRESH_JOBS_PER_RETRY:
                    # Append just one retry behind existing work. Never flood
                    # the queue with retries ahead of fresh snapshots.
                    self.schedule_presence(user_id)
                    fresh_jobs = 0
            try:
                timeout = None if not retries else max(0, next_retry - now)
                async with asyncio.timeout(timeout):
                    job = await self.presence_queue.get()
            except TimeoutError:
                continue
            try:
                if isinstance(job, int):
                    # Remove before awaiting: changes during delivery must
                    # enqueue another update, even for this same user.
                    self.pending_presence.discard(job)
                    online = job in self.active_connections
                    result = await notify_presence_safely(self, job, online)
                    if result is PresenceResult.RETRY:
                        previous_delay = self.retry_presence.get(job, (0, 0))[0]
                        delay = min(self.MAX_RETRY_INTERVAL, max(self.RETRY_INTERVAL, previous_delay * 2))
                        self.retry_presence[job] = (delay, asyncio.get_running_loop().time() + delay)
                    else:
                        self.retry_presence.pop(job, None)
                        if result is PresenceResult.FAILED:
                            logger.error(
                                "Presence update for user %s (online=%s) was not delivered: "
                                "non-transient failure; fix the error and reconnect clients to resync",
                                job, online,
                            )
                else:
                    socket, user_id, completed = job
                    if not completed.done():
                        result = await send_presence_snapshot_safely(self, socket, user_id)
                        if not completed.done():
                            completed.set_result(result)
            except asyncio.CancelledError:
                if isinstance(job, int) and not self.stopping:
                    # An explicit restart after unexpected cancellation must
                    # reconcile the state whose delivery was interrupted.
                    self.schedule_presence(job)
                elif isinstance(job, tuple):
                    if job[0] in self.active_connections.get(job[1], set()):
                        self.disconnect(job[0], job[1])
                        await self.close_socket(job[0])
                raise
            finally:
                if isinstance(job, tuple):
                    if not job[2].done():
                        job[2].set_result(False)
                    if self.snapshot_pending.get(job[0]) is job[2]:
                        self.snapshot_pending.pop(job[0], None)
                self.presence_queue.task_done()
                fresh_jobs += 1

    def schedule_snapshot(self, websocket: WebSocket, user_id: int):
        """Coalesce refreshes into the same FIFO as presence transitions."""
        if websocket not in self.active_connections.get(user_id, set()):
            return None
        pending = self.snapshot_pending.get(websocket)
        if pending is None or pending.done():
            pending = asyncio.get_running_loop().create_future()
            self.snapshot_pending[websocket] = pending
            self.presence_queue.put_nowait((websocket, user_id, pending))
        return pending

    async def initialize(self, websocket: WebSocket, user_id: int) -> bool:
        if self.presence_worker is None or self.presence_worker.done():
            raise RuntimeError("Presence dispatcher is not running")
        if websocket not in self.active_connections.get(user_id, set()):
            return False
        completed = self.schedule_snapshot(websocket, user_id)
        try:
            async with asyncio.timeout(self.INITIALIZE_TIMEOUT):
                return await completed
        except TimeoutError:
            self.disconnect(websocket, user_id)
            await self.close_socket(websocket)
            return False
        except asyncio.CancelledError:
            self.disconnect(websocket, user_id)
            await self.close_socket(websocket)
            raise

    async def connect(self, websocket: WebSocket, user_id: int) -> bool:
        if self.stopping:
            raise RuntimeError("Presence dispatcher is stopping")
        admissions = self.initialization_admissions
        if (len(admissions) >= self.MAX_INITIALIZATIONS or
                sum(owner == user_id for owner in admissions.values()) >= self.MAX_INITIALIZATIONS_PER_USER):
            await self.close_socket(websocket, code=1013)
            raise WebSocketDisconnect(code=1013)
        admissions[websocket] = user_id
        try:
            async with asyncio.timeout(self.SEND_TIMEOUT):
                await websocket.accept()
        except BaseException:
            admissions.pop(websocket, None)
            raise
        if self.stopping:
            admissions.pop(websocket, None)
            await self.close_socket(websocket)
            raise WebSocketDisconnect(code=1011)

        was_offline = user_id not in self.active_connections

        if was_offline:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)
        self.initializing.add(websocket)
        self.send_locks[websocket] = asyncio.Lock()
        self.disconnected[websocket] = asyncio.Event()
        if was_offline:
            self.schedule_presence(user_id)
        return was_offline


    def discard_initialization(self, websocket: WebSocket):
        self.initialization_admissions.pop(websocket, None)
        # Physically remove cancelled queue entries: tombstones would still
        # retain sockets and could grow without bound under reconnect churn.
        # No await; keep unfinished-task accounting valid for queue.join().
        jobs = [self.presence_queue.get_nowait() for _ in range(self.presence_queue.qsize())]
        for job in jobs:
            if isinstance(job, tuple) and job[0] is websocket:
                if not job[2].done():
                    job[2].set_result(False)
            else:
                self.presence_queue.put_nowait(job)
        for _ in jobs:
            self.presence_queue.task_done()


    def disconnect(self, websocket: WebSocket, user_id: int) -> bool:
        if user_id not in self.active_connections:
            return False

        connections = self.active_connections[user_id]

        if websocket not in connections:
            return False

        connections.discard(websocket)
        self.discard_initialization(websocket)
        self.session_tokens.pop(websocket, None)
        self.friend_ids.pop(websocket, None)
        pending = self.snapshot_pending.pop(websocket, None)
        if pending is not None and not pending.done():
            pending.set_result(False)
        self.initializing.discard(websocket)
        self.send_locks.pop(websocket, None)
        disconnected = self.disconnected.pop(websocket, None)
        if disconnected is not None:
            disconnected.set()

        if not connections:
            del self.active_connections[user_id]
            self.schedule_presence(user_id)
            return True

        return False

    async def disconnect_session(self, token: str):
        """Revoke local delivery before awaiting any transport work.

        Match the login session, not the user: independent logins stay online.
        A connection registered after this scan is still checked before its
        initial snapshot, so no permanent cache of revoked tokens is needed.
        """
        sockets = []
        for user_id, connections in list(self.active_connections.items()):
            for socket in connections.copy():
                if self.session_tokens.get(socket) == token:
                    sockets.append((socket, self.send_locks[socket]))
                    self.disconnect(socket, user_id)

        async def close(socket, lock):
            try:
                async with asyncio.timeout(self.SEND_TIMEOUT):
                    async with lock:
                        await self.close_socket(socket, code=1008)
            except TimeoutError:
                await self.close_socket(socket, code=1008)

        # A stalled tab must not serialize/delay closure of its healthy peers.
        await asyncio.gather(*(close(socket, lock) for socket, lock in sockets))

    async def check_session(self, websocket: WebSocket, user_id: int) -> bool:
        """Called under the socket's send lock; failures revoke local membership.

        The /ws route binds its authenticated token before initialization or
        any outbound frame. Missing bindings fail closed as invalid sessions.
        """
        token = self.session_tokens.get(websocket)
        try:
            async with asyncio.timeout(DB_TIMEOUT):
                authenticated_id = await run_in_threadpool(authenticate_websocket, token)
        except (SQLAlchemyError, OSError, TimeoutError):
            logger.error("WebSocket session revalidation unavailable")
            code = 1011
        else:
            if authenticated_id == user_id:
                return True
            code = 1008
        self.disconnect(websocket, user_id)
        await self.close_socket(websocket, code=code)
        return False

    async def revalidate(self, websocket: WebSocket, user_id: int) -> bool:
        lock = self.send_locks.get(websocket)
        if lock is None:
            return False
        try:
            async with asyncio.timeout(self.SEND_TIMEOUT):
                async with lock:
                    if websocket not in self.active_connections.get(user_id, set()):
                        return False
                    return await self.check_session(websocket, user_id)
        except TimeoutError:
            self.disconnect(websocket, user_id)
            await self.close_socket(websocket)
            return False

    async def close_socket(self, websocket: WebSocket, code: int = 1011):
        try:
            async with asyncio.timeout(self.CLOSE_TIMEOUT):
                await websocket.close(code=code)
        except (WebSocketDisconnect, OSError, RuntimeError, TimeoutError):
            pass

    async def send_frame(self, websocket: WebSocket, user_id: int, event: dict, *, snapshot=False):
        lock = self.send_locks.get(websocket)
        if lock is None:
            return False
        write_started = False
        try:
            async with asyncio.timeout(self.SEND_TIMEOUT):
                async with lock:
                    if websocket not in self.active_connections.get(user_id, set()):
                        return False
                    if not snapshot and websocket in self.initializing:
                        return False
                    if not await self.check_session(websocket, user_id):
                        return False
                    if websocket not in self.active_connections.get(user_id, set()):
                        return False
                    write_started = True
                    await websocket.send_json(event)
                    if snapshot and websocket in self.active_connections.get(user_id, set()):
                        # No await between finishing the snapshot and allowing
                        # live delivery. State changes during send are queued.
                        self.initializing.discard(websocket)
                        self.initialization_admissions.pop(websocket, None)
                    return True
        except asyncio.CancelledError:
            # Waiting for somebody else's write does not damage this socket.
            # An interrupted transport write may leave a partial frame.
            if write_started and websocket in self.active_connections.get(user_id, set()):
                self.disconnect(websocket, user_id)
                await self.close_socket(websocket)
            raise

    async def send_event(self, websocket: WebSocket, user_id: int, event: dict):
        try:
            return await self.send_frame(websocket, user_id, event)
        except (WebSocketDisconnect, OSError, RuntimeError, TimeoutError):
            self.disconnect(websocket, user_id)
            await self.close_socket(websocket)
            return False


    async def send_to_user(self, user_id: int, event: dict):
        connections = self.active_connections.get(user_id)

        if not connections:
            return

        for connection in connections.copy():
            await self.send_event(connection, user_id, event)
