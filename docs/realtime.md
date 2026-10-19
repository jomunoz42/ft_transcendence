# Realtime development

`/ws` is a server-driven presence connection authenticated with the existing
`myplaylist_session` cookie. Client text and binary frames are ignored; there is
no echo, broadcast command, or client-supplied presence update.

## Origins and HTTPS

Set `WEBSOCKET_ALLOWED_ORIGINS` in the backend environment (Compose loads `.env`):

```dotenv
# Local Vite development; also the defaults when the variable is absent.
WEBSOCKET_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
# Deployment example: replace the local list with your actual frontend origin.
# WEBSOCKET_ALLOWED_ORIGINS=https://myplaylist.example
```

Values are comma-separated exact **HTTP(S) browser origins**, including any
non-default port. Do not use WebSocket URLs, paths, trailing slashes, credentials,
or wildcards. Invalid configuration fails at application import. An explicitly
empty value rejects all connections. Missing, `null`, and unlisted Origin headers
are rejected before database authentication. Restart the backend after changing
configuration.

Serve the frontend over HTTPS and connect to `wss://` in deployment, forwarding
WebSocket upgrades through the HTTPS reverse proxy. Origin configuration does
not terminate TLS. The existing login cookie is `Secure`; use local HTTPS when
exercising the complete browser login flow. This change does not weaken cookie
settings or add HTTP CORS configuration.

## Presence protocol

The first application frame is a private snapshot:

```json
{"type":"presence_snapshot","data":{"online_user_ids":[7,12]}}
```

The client replaces its online-friends set with this list. Subsequent transitions
look like:

```json
{"type":"presence","data":{"user_id":7,"online":false}}
```

Only accepted, non-deleted friends are selected through `list_friends`. A user
is online while at least one registered connection remains. Closing one tab or
logging out one login session preserves online presence if another connection
with a valid session remains.

## Hybrid session validation and logout

Session validity is checked at the handshake, before every outbound application
frame, and every **10 seconds** while the socket remains connected. Periodic
checks run per socket; tabs do not share a validation cache. Incoming client
frames cannot postpone the deadline. Invalid or missing sessions close with
`1008`. Database errors or validation timeouts fail closed with `1011`, without
sending the protected frame. Reconnect after the database recovers.

HTTP logout deletes only the presented login session and commits, then invokes
an injected realtime notifier. The existing `end_session` authentication helper
is unchanged. `app/main.py` exposes the manager through application state;
`app/realtime/notifications.py` uses AnyIO's `from_thread.run` to hand the
synchronous FastAPI route's notification to its async event loop and wait for
cleanup. Neither the auth router nor the notifier imports `app.main`.

The manager removes **all sockets for that token**, before awaiting transport
work, and wakes their endpoints immediately, including pending initialization.
Separate login sessions belonging to the same user remain connected. Socket
closes run concurrently and respect existing send locks and timeouts, so a slow
tab does not delay closing its healthy peers. The HTTP response waits for bounded
cleanup rather than launching an untracked background task. A failed database
commit sends no notification. A notification failure is logged without the token;
the cookie is still cleared, and database-backed checks remain the fallback.

Logout normally closes idle sockets immediately after the committed notification,
without waiting for either polling interval. Expiry, account deletion, revocation
outside this route, and missed notifications are detected by the next 10-second
session check or an earlier outbound check. Allow additional database/lock time;
validation/lock work is bounded by the existing five-second send timeout and
transport closure by one more second. These are application timeouts, not a
guarantee that a synchronous database operation stops running in its worker thread.

Connection/logout races have two protections: a socket registered after a logout
notification must still pass a fresh database check before its initial snapshot;
a socket removed during an outbound validation cannot send using that lookup's
stale result because membership is checked again immediately before writing.
A frame already authorized and in flight when logout commits cannot be recalled.
No frame is authorized solely by a cached handshake result. Client frames currently
perform no actions; future client commands must validate authorization before
execution as well.

## Independent friendship refresh

Each socket schedules a friendship refresh every **5 seconds**, independently of
its 10-second session deadline. The serialized presence queue coalesces outstanding
refreshes per socket; it does not enqueue another copy while one is pending. If
the accepted, non-deleted friend IDs changed, a private snapshot replaces that
socket's online-friends set. All tabs refresh independently. An unchanged friend
set generates no duplicate snapshot, although the lookup still runs.

There is currently no friendship acceptance HTTP route. Reciprocal requests in
`send_friend_request` accept the friendship; refresh observes the change only
after commit, regardless of which future route performs it. Rollbacks do not emit
presence. Refresh normally occurs on the next five-second deadline plus queue and
lookup time. Transient refresh lookup failures retry at the next deadline; initial
snapshot failures still close the connection. Deleting a friend also removes them
from subsequent snapshots. A future acceptance route can trigger refresh after
commit while retaining polling as a fallback.

Idle steady-state application reads are approximately **0.3 per socket per second**:
`1/10` for sessions plus `1/5` for friendships, assuming the queue keeps up. Each
outbound frame adds a session lookup. The configured `pool_pre_ping=True` normally
adds a `SELECT 1` on each reused database connection checkout, bringing the idle
estimate to about 0.6 SQL reads per socket per second, excluding transaction
control, initial connections, presence transitions, retries, and HTTP traffic.
Pooled connections are reused; there is no dedicated PostgreSQL connection per
WebSocket. Refresh work is serialized and can lag under load. Shared per-session
validation or per-user friendship refresh could reduce duplicate tab work later.

## Process boundary

Connections, notifications, and presence ordering remain **process-local**. Run a
single backend worker with the current design. Direct logout notification reaches
only that process; other processes would detect revocation through their database
checks, but their presence views would still be incomplete. Multiple workers need
a separate design for shared presence and cross-worker notification. No broker,
Redis, database schema changes, or new infrastructure is introduced here.

## Code and tests

- `app/main.py`: application lifecycle, handshake, and route wiring.
- `app/realtime/manager.py`: connection membership, locks, session checks,
  coalesced snapshot work, and presence retries.
- `app/realtime/presence.py`: friend filtering and presence event construction.
- `app/realtime/config.py`: origin configuration.
- `app/realtime/notifications.py`: injected synchronous-to-async logout notifier.

Run `make migrate` and `make test` with the Compose PostgreSQL stack. Alternatively,
point `DATABASE_URL` at an isolated PostgreSQL database, then run from `backend/`:

```sh
.venv/bin/alembic upgrade head
.venv/bin/pytest -q
```

The PostgreSQL WebSocket/lifecycle tests create and remove temporary schemas.
Transport tests exercise concurrency with server-originated test probes; these
probes are not client commands. Tests cover forbidden client broadcasts, origin
matching, deleted accounts, immediate session-scoped logout, failed commits and
notification fallback, logout/connection/delivery races, expiry, multiple tabs
and independent sessions, independent friendship refresh, committed/rolled-back
acceptance, and delivery/refresh resilience.
