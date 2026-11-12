# Frontend

Frontend workspace for **MyPlaylist / ft_transcendence**, primarily maintained
by Pedro.

## Stack

- React
- TypeScript
- Vite
- Node.js 22
- Docker

## Frontend features

- Responsive app shell with Home, Friends, Settings, login, registration,
  and member profile views.
- Account forms with native constraints, client-side checks, and accessible
  field and request error feedback.
- Editable, manually entered Top 10 lists, with rank controls and duplicate
  checks.
- Member profiles with Top 10 and comments through the profile API.
- WebSocket presence snapshots and updates, with unknown/reconnecting states
  when the connection is unavailable.
- Profile display-name and Top 10 visibility settings, plus light/dark themes.
- Keyboard skip link and focus indicators, semantic navigation, reduced-motion
  support, and mobile layouts.

Friend-request management, song search, and chat are not implemented in the
current frontend because the corresponding backend routes are not available.
The Friends view currently lists member profiles and presence rather than
providing a complete friends roster or request workflow.

## Styling changes and Docker

After changing the frontend dependencies, rebuild and recreate the frontend
service so its dedicated `frontend_node_modules` volume is initialized from the
updated image:

```bash
docker compose up -d --build frontend
```

For a local non-Docker install, run `npm ci` from this directory, then use
`npm run dev` or `npm run build`.

## Local HTTPS and presence

The session cookie is `Secure`, so use a trusted local HTTPS origin to test
login and WebSocket presence reliably. Vite proxies `/api` and `/ws` to the
backend; the WebSocket proxy preserves the upgrade request.

With `mkcert` installed and its local CA trusted, create a localhost certificate
outside the repository:

```bash
mkcert -install
mkcert -cert-file /tmp/myplaylist-local.pem -key-file /tmp/myplaylist-local-key.pem localhost
```

Set `WEBSOCKET_ALLOWED_ORIGINS` in the root `.env` to include
`https://localhost:5173`, then start the database and backend with Compose:

```bash
docker compose up -d postgres backend
```

Run Vite directly from `frontend/` so it can read the certificate. Its default
API proxy target is `http://localhost:8000`, which reaches the backend port
published by Compose:

```bash
VITE_DEV_TLS_CERT=/tmp/myplaylist-local.pem VITE_DEV_TLS_KEY=/tmp/myplaylist-local-key.pem npm run dev -- --host 0.0.0.0
```

Open `https://localhost:5173`. Do not weaken the cookie or commit the local
private key. The regular Compose frontend remains available over HTTP for UI
work, but browsers may not send its Secure cookie consistently over that
origin.

## Run

From `frontend/`:

```bash
docker build -t transcendence-frontend .
docker run --rm -p 5173:5173 transcendence-frontend
