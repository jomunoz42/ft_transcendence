# Frontend

Frontend workspace for **ft_transcendence**, primarily maintained by Pedro.

## Stack

- React
- TypeScript
- Vite
- Node.js 22
- Docker

## Current State

The frontend has been initialized and intentionally left as a blank React application, ready for development.

The Docker image has been built and tested successfully.

No UI architecture, styling system, component library, routing, or state-management solution has been imposed yet.

## Run

From `frontend/`:

```bash
docker build -t transcendence-frontend .
docker run --rm -p 5173:5173 transcendence-frontend