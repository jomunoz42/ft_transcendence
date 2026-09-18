# Database Development

Database workspace for **ft_transcendence**, maintained by André.

## Stack

- PostgreSQL 17 (Alpine image, unmodified)
- SQLAlchemy 2.x + Alembic (integrated in ticket 03; migrations will live under `backend/`, since they are driven by the Python models)

## Contents

| File | Purpose |
| --- | --- |
| `db-schema.md` | Schema design: the 7 tables, constraints, and the placeholder decisions behind them |
| `db-check.sh` | Runnable check for the Postgres container — connects with the `.env` credentials, writes a row, restarts the stack, verifies the row survived |

## Why `docker-compose.yml` is at the repo root, not here

It orchestrates the whole project — database, backend, and frontend are separate services in one file, so a single command deploys everything (a subject requirement). The database still gets its own container; only the compose file that starts it is shared.

## No Dockerfile here, on purpose

The stock `postgres:17-alpine` image is used as-is. A Dockerfile would only be needed to add extensions, a custom locale, or init scripts — none of which are required yet. If init SQL becomes necessary, mount it into `/docker-entrypoint-initdb.d/` from this folder rather than building a custom image.

## Run

Credentials come from `.env` at the repo root (copy `.env.example` first). Never commit `.env`.

```bash
make up          # start the stack
make db-check    # verify the DB connects and persists across a restart
make down        # stop the stack
```

`db-check.sh` works with either `docker compose` (v2) or `docker-compose` (v1); it detects which is installed.
