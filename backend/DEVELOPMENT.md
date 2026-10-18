# Backend Development

Backend workspace for **ft_transcendence**, primarily maintained by Victor.

## Stack

- Python 3.14
- FastAPI
- Uvicorn
- Docker

PostgreSQL and SQLAlchemy are wired up (ticket 02). Alembic migrations follow in ticket 03.

## Current State

The backend has been initialized with a minimal FastAPI application.

`GET /health` queries the database on every call: 200 with `{"status": "ok", "database": "ok"}` when it is reachable, 503 with `{"status": "error", "database": "unreachable"}` when it is not. A readiness check that stays green while the database is down would be useless.

`app/db.py` is the single place an engine is built and sessions are handed out. Anything needing a session depends on `get_session`; nothing else creates its own engine.

The backend has been tested both locally and inside Docker.

Database and authentication details are documented under `docs/andre_docs_code/`;
this page focuses on running and testing the backend transport.

## WebSocket Transport

`ws://localhost:8000/ws` accepts WebSocket connections. Clients send plain text
frames. Each received text frame is broadcast to every currently connected
client, including its sender, as JSON:

```json
{
  "type": "message",
  "data": {
    "text": "the original text"
  }
}
```

Before accepting, `/ws` requires an Origin of `http://localhost:5173` or
`http://127.0.0.1:5173` and the `myplaylist_session` cookie. The raw cookie is
passed to the existing `user_for_token()` lookup in a threadpool: PostgreSQL
stores its SHA-256 hash, and expired/revoked sessions and deleted users are
rejected. No token is put in the URL or logged. Login/session creation remains
in the existing authentication layer; the WebSocket does not create sessions.

`ConnectionManager` tracks a set of sockets per authenticated user. The first
registration schedules online; removing the last socket schedules offline.
Duplicate cleanup is harmless. Presence uses accepted friendships in either
direction; pending, declined, blocked and unrelated users receive no presence.

FastAPI lifespan owns one presence dispatcher. Its queue coalesces user IDs
and resolves their current state when processing, instead of replaying stale
booleans. Failed-send cleanup only queues changes; it never recursively sends
notifications. Transient lookup failures (timeouts, connection failures and
retryable PostgreSQL errors) retry after 1, 2, 4, 8, 16, then 30 seconds, capped
at 30 seconds. A failed offline update remains pending until recovery; there is
no attempt-count limit that would silently lose it. Only one due retry is
appended behind fresh work per eight processed jobs (or when the queue is
empty), so retries and new snapshots both get a turn. Programming errors and
non-transient database errors are logged without automatic retries; operators
must fix the error and reconnect clients to resynchronize. Intermediate states
can be coalesced, and retries may repeat the same state; presence events are
state assignments, not an audit log.

Every socket is registered immediately but excluded from live delivery until
its initial `{"type":"presence_snapshot","data":{"online_user_ids":[...]}}`
has been sent. Snapshots and live `{"type":"presence","data":{"user_id":1,
"online":true}}` events use the same dispatcher. Changes during snapshot
lookup/delivery remain queued and are processed afterward. Per-socket locks
also serialize independent message broadcasts with snapshot/presence writes.
Snapshot lookup or send failure removes and closes that socket; a surviving
tab remains online. Clients should reconnect after a failed initialization.
Ordinary messages sent before a socket becomes ready are not guaranteed to be
delivered; there is no initialization message buffer.

At most 64 initializations may be pending globally and four per user, including
accepts in flight. Excess connections are rejected before acceptance (ASGI
close code 1013; an HTTP upgrade denial on the wire). Ready tabs do not consume
this capacity. Success, failure, timeout and cancellation release the slot;
cancelled initialization jobs are removed from the queue, not left as tombstones.

Deadlines: database awaits are limited to 6 seconds; each accept/send (including
waiting for its write lock) to 5 seconds; closing to 1 second; initialization
including queue wait to 20 seconds. These are realtime coroutine deadlines;
the shared database engine policy is unchanged. Cancelling an await cannot
kill an already-running synchronous database call: its thread/session may
remain occupied until the driver returns. No statement or pool-checkout limits
are imposed on authentication, registration or other backend queries here.
Slow sockets are removed and closed. One slow operation can delay other users
until its deadline; this is the deliberate tradeoff for a single dispatcher.

Shutdown cancels the dispatcher, resolves pending initialization requests and
closes registered sockets. State and retries are in memory, so this design is
for one backend process only. Authentication is checked at handshake time;
revoking a session does not yet disconnect an already-open socket. Profile
`is_online`/`last_seen_at` columns are not maintained by this transport.

## Tests

```bash
make test        # from the repo root
```

Runs pytest inside the backend container. `backend/` is bind-mounted into the image, so edits do not need a rebuild.

Run only the transport tests without starting PostgreSQL:

```bash
docker compose run --rm --no-deps backend pytest tests/test_websocket.py
```

The transport tests exercise the FastAPI ASGI application in-process. The
query tests use isolated SQLite databases; they are not PostgreSQL verification.
Run the focused suite from `backend/` with:

```bash
DATABASE_URL=sqlite:///:memory: python -m pytest -q tests/test_connection_manager.py tests/test_websocket.py tests/test_websocket_auth.py tests/test_presence.py tests/test_presence_dispatcher.py tests/test_presence_resilience.py tests/test_websocket_postgres.py
```

With a PostgreSQL `DATABASE_URL`, `test_websocket_postgres.py` instead exercises
real committed sessions, the cookie handshake and friendship visibility in a
temporary schema (CREATE SCHEMA permission required). It skips explicitly for
SQLite. It does not replace the project's PostgreSQL migration/session tests.

## Manual WebSocket Check

1. Run `make up` from the repository root.
2. Open `http://localhost:5173` in two browser tabs.
3. Establish a valid session using the authentication layer and set its raw
   token as the `myplaylist_session` cookie for the backend host, with path `/`.
   Use the same hostname consistently (`localhost` and `127.0.0.1` differ).
   Click **Connect WebSocket** in both tabs. The browser sends the cookie.
4. Send a message from either tab and confirm that the same message appears in
   both tabs, including the sender.
5. Close one tab, then send another message from the remaining tab and confirm
   that it still receives the broadcast.

## Run Locally

From `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Models
![alt text](assets/models.png)

## Flow
![alt text](assets/flow.png)

## Tree
![alt text](assets/tree.png)

## Coding practices

#### Routes
```python
from fastapi import APIRouter, Depends, HTTPException, responses

router = APIRouter()

@router.get("/")
def get_all():
	...
```

#### HTTP Exceptions
```python
# /app/crud/xxx
class Error<ErrorName>(Exception):
    pass

...
except:
	raise Error<ErrorName>("Error when reading profiles")

# /app/routes/xxx
from fastapi import HTTPException

...
except Exception as error:
	raise HTTPException(status_code=400, detail=str(error))
```
