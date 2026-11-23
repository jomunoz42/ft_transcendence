

# ft_transcendence

## Description

TODO: Add the final project name, concept, goal, and key features.

ft_transcendence must be a web application with a frontend, backend, database, secure user management, multi-user support, Privacy Policy and Terms of Service pages, and at least 14 validated module points.

## Project Management

TODO: Describe how the team organizes work, distributes tasks, reviews code, communicates, and tracks blockers.

## Technical Stack

| Area | Choice | Justification |
| --- | --- | --- |
| Frontend | React + Vite + TypeScript | Component-based frontend with fast local development. |
| Backend | Python + FastAPI | Lightweight API framework with WebSocket support. |
| Database | PostgreSQL | Relational database for users, profiles, social data, and application state. |
| Styling solution | TODO | TODO |
| Deployment | Docker Compose | Runs the application services through a single development stack. |

## Database Schema

TODO: Add a visual representation or clear text description of the database schema, including tables/collections, key fields, data types, and relations.

## Features List

| Feature | Description | Contributor(s) |
| --- | --- | --- |
| TODO | TODO | TODO |

## Modules

Major modules count as 2 points. Minor modules count as 1 point. The project must reach at least 14 validated module points.

| Module | Type | Points | Justification | Implementation | Contributor(s) |
| --- | --- | ---: | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | TODO |

Total planned points: TODO

## Individual Contributions

| Member | Contributions | Challenges and Solutions |
| --- | --- | --- |
| jomunoz | TODO | TODO |

## Instructions

### Prerequisites

- Docker with Docker Compose
- Make

### Environment

Create the local environment file from the committed template:

```bash
cp .env.example .env
```

Fill in the local values in `.env`. This file contains local configuration and secrets and must remain ignored by Git.

See [realtime development](docs/realtime.md) for WebSocket origins, HTTPS,
presence events, logout behavior, and integration tests.

### Run

Build and start the complete application:

```bash
make up
```

Compose waits for PostgreSQL to become healthy, then the backend applies pending
Alembic migrations before starting the API. No manual `make migrate` is needed.
Each backend start checks for pending migrations; an up-to-date database keeps
its existing data. If migration fails, the backend logs the error and exits
without serving requests (Compose's restart policy retries it).

Open `https://localhost` (or `https://127.0.0.1`) after trusting the local
certificate as described below. Caddy redirects HTTP on port 80 to HTTPS on
port 443, serves Vite, and forwards `/api/*` and `/ws` to FastAPI, including
WebSocket upgrades. API calls use the page's HTTPS origin and WebSockets use WSS.

Vite and FastAPI have no published host ports; ports 5173 and 8000 are internal
to Docker. Source mounts, Vite hot reload, and backend reload remain available.
Prometheus still scrapes `http://backend:8000/metrics` inside Docker. Existing
`.env` files should set
`WEBSOCKET_ALLOWED_ORIGINS=https://localhost,https://127.0.0.1`; `BACKEND_PORT`
is no longer used. Keep the same hostname throughout login and WebSocket use.

### Trust local HTTPS (once per machine/browser)

Caddy generates certificates automatically and keeps its local CA in the
`caddy_data` volume. After `make up`, run in another terminal:

```bash
mkdir -p .scratch
docker compose exec -T caddy cat /data/caddy/pki/authorities/local/root.crt > .scratch/caddy-root.crt
```

Use `docker-compose` instead if using standalone Compose v1. On Debian/Ubuntu,
trust this public root certificate for command-line clients:

```bash
sudo cp .scratch/caddy-root.crt /usr/local/share/ca-certificates/ft-transcendence-caddy.crt
sudo update-ca-certificates
```

In Chrome, open Settings → Privacy and security → Security → Manage certificates
and import `.scratch/caddy-root.crt` into the local trusted authorities for
identifying websites, then restart Chrome. Other systems can import the same
certificate into their system trust store; see
[Caddy's local HTTPS instructions](https://caddyserver.com/docs/running#local-https-with-docker).
Only export `root.crt`, never the CA private key. `.scratch` is ignored by Git.
`make down` preserves the CA; deleting `caddy_data` (including via `make db-reset`)
requires exporting and trusting the new CA again.

Verify TLS without bypassing certificate validation:

```bash
curl --cacert .scratch/caddy-root.crt -I https://localhost
curl --cacert .scratch/caddy-root.crt -i https://localhost/api/v1/auth/me
```

The second request should return `401` when logged out. In Chrome, verify a trusted
address bar, registration/login/logout, the `Secure` session cookie, HTTPS API
requests, a `wss://localhost/ws` connection with status `101` after login, and
Vite hot reload. Check DevTools for certificate, mixed-content, or WebSocket
errors. Direct HTTP access on ports 8000 and 5173 should fail.

### Stop and development commands

To stop the application:

```bash
make down
```

Useful development commands:

```bash
make logs
make status
make test
make migrate
```

### Fresh-deployment smoke test

Use a separate checkout and a new, unique Compose project name to isolate
the database and Caddy certificate volumes. Ensure ports 80, 443, 5432,
3000 and 9090 are free. Never run `make db-reset` or `down -v` against
your normal project.

In the disposable checkout, configure `.env` from `.env.example`, including
`GRAFANA_ADMIN_PASSWORD` and the HTTPS WebSocket origins, then:

```bash
# Save the unique project name in this checkout's .env for all terminals.
printf '\nCOMPOSE_PROJECT_NAME=ft48-smoke-%s\n' "$(date +%s)" >> .env
make up
```

Wait for Alembic migration logs followed by Uvicorn's startup message.
Caddy uses its own local CA for this isolated Compose project. Export the
certificate using the instructions in "Trust local HTTPS" above, from this
checkout, then run:

```bash
curl --cacert .scratch/caddy-root.crt --fail-with-body https://localhost/
curl --cacert .scratch/caddy-root.crt --fail-with-body -i https://localhost/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"deployment-smoke@example.com","password":"smoke-password-48","display_name":"Deployment smoke"}'
```

Registration must return HTTP 201; save the returned user ID. Run `make down`
and then `make up` again, keeping the same `.env` and volumes. Once ready:

```bash
curl --cacert .scratch/caddy-root.crt --fail-with-body -i https://localhost/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"deployment-smoke@example.com","password":"smoke-password-48"}'
```

Login must return HTTP 200 with the same user ID and display name, proving the
account and profile survived. Stop the disposable stack with `make down`.
Do not remove the normal project's volumes.

## Resources

TODO: Add documentation, articles, tutorials, and references used by the team.

### AI Usage

TODO: Explain which AI tools were used, for which tasks, and which parts of the project were AI-assisted.

## Notes

The subject and correction sheet PDFs are kept in the repository root for reference.

