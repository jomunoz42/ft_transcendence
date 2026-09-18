# Backend Development

Backend workspace for **ft_transcendence**, primarily maintained by Victor.

## Stack

- Python 3.14
- FastAPI
- Uvicorn
- Docker

PostgreSQL, SQLAlchemy and Alembic will be integrated in the next infrastructure stage.

## Current State

The backend has been initialized with a minimal FastAPI application.

`GET /health` is available as a basic service health check.

The backend has been tested both locally and inside Docker.

No application architecture, API structure, database models, authentication, or business logic has been imposed yet.

## Run Locally

From `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload