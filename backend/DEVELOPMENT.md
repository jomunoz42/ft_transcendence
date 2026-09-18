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

No API structure, database models, authentication, or business logic has been imposed yet, beyond the database connection above.

## Tests

```bash
make test        # from the repo root
```

Runs pytest inside the backend container. `backend/` is bind-mounted into the image, so edits do not need a rebuild.

## Run Locally

From `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload