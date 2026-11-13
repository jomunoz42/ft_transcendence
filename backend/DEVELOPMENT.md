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

`/ws` provides authenticated, server-driven friend presence. The default
transport URL is `ws://localhost:8000/ws`; browser login uses a Secure cookie,
so use the HTTPS setup described in the contract when testing the full flow.
Client text and binary frames are ignored; there is no echo or broadcast command.

Start with the [frontend presence contract](../docs/presence-contract.md) for:

- Development URLs, allowed origins, and browser cookie authentication.
- Exact initial/replacement snapshot and online/offline event schemas.
- Multiple tabs, session expiry, logout, and reconnect behavior.
- A framework-independent JavaScript client and two-account manual test.

The [realtime architecture](../docs/realtime.md) covers the process-local
connection manager, serialized presence dispatcher, session validation,
friendship refresh, timeouts, retries, and limitations. The
[issue #7 audit](../docs/presence-audit.md) maps acceptance criteria to tests.

Presence comes from registered sockets, not the profile `is_online` or
`last_seen_at` columns. Use one backend worker. Authentication is checked before
acceptance, before every outbound frame, and periodically while connected.
Committed logout immediately disconnects sockets for that session; independent
login sessions remain connected.

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
DATABASE_URL=sqlite:///:memory: python -m pytest -q tests/test_connection_manager.py tests/test_websocket.py tests/test_websocket_auth.py tests/test_presence.py tests/test_presence_dispatcher.py tests/test_presence_resilience.py tests/test_realtime_config.py tests/test_websocket_postgres.py tests/test_realtime_lifecycle.py
```

With a PostgreSQL `DATABASE_URL`, `test_websocket_postgres.py` instead exercises
real committed sessions, the cookie handshake and friendship visibility in a
temporary schema (CREATE SCHEMA permission required). It skips explicitly for
SQLite. It does not replace the project's PostgreSQL migration/session tests.

## Manual WebSocket Check

Follow the [two-account browser recipe](../docs/presence-contract.md#reproducible-two-account-browser-test-no-frontend-changes).
It uses real login cookies, committed accepted friendships, and the documented
presence frames. It does not require frontend changes or client broadcasts.

## Run Locally

From `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Models
![alt text](docs/victor_assets/models.png)

## Flow
![alt text](docs/victor_assets/flow.png)

## Tree
![alt text](docs/victor_assets/tree.png)

## Coding practices

#### Routes
```python
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("")
def get_all():
	...
```

#### Error handling

All errors live in `app/errors/__init__.py`. Import the module, raise directly:

```python
from app import errors

# Pre-built HTTPException instances — no parentheses
raise errors.HTTP_404_NOT_FOUND
raise errors.HTTP_422_UNPROCESSABLE_CONTENT
raise errors.HTTP_409_CONFLICT

# Dynamic errors — functions that return an HTTPException
raise errors.http_422_registration("email", "not a valid email address")
```

No custom exception classes. No `try/except` wrappers to convert exceptions into
HTTP responses. Do not catch DB errors in crud functions — let them bubble up as
500s with a full traceback in server logs.

#### Session commits

Routes do not call `session.commit()` manually. Instead, attach a `commit_session`
dependency to the router:

```python
def commit_session(session: Session = Depends(get_session)):
    yield
    session.commit()

router = APIRouter(dependencies=[Depends(commit_session)])
```

The commit runs automatically after a successful response. If any exception is
raised, the yield never reaches `session.commit()`, so nothing is committed.
Rule functions use `session.flush()` to surface DB errors early without committing.
