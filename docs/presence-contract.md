# Friends presence: integration contract for Pedro (#27)

Backend owner: João, [issue #7](https://github.com/jomunoz42/ft_transcendence/issues/7).
Frontend owner: Pedro, [issue #27](https://github.com/jomunoz42/ft_transcendence/issues/27).
Verified against the implementation from PRs #24 and #26. See the
[acceptance audit](presence-audit.md) and [backend architecture](realtime.md).

## Connect and authenticate

The endpoint is **`/ws`**, without an API prefix, query token, or subprotocol.

| Environment | WebSocket URL | Browser page origin |
| --- | --- | --- |
| Default development services | `ws://localhost:8000/ws` | `http://localhost:5173` |
| Equivalent loopback hostname | `ws://127.0.0.1:8000/ws` | `http://127.0.0.1:5173` |
| HTTPS manual setup below | `wss://localhost:8443/ws` | `https://localhost:8443` |
| Deployment behind one HTTPS origin | `wss://<application-host>/ws` | `https://<application-host>` |

`BACKEND_PORT` can change the development backend port. Use the same hostname
throughout login and WebSocket connections: `localhost` and `127.0.0.1` have
different cookies. Run **one backend worker**; presence is process-local.

1. `POST /api/v1/auth/login` with JSON
   `{"email":"alex@example.test","password":"local-demo-password"}`.
2. A successful login returns the public user, e.g.
   `{"id":7,"email":"alex@example.test","display_name":"Alex"}`, and sets
   `myplaylist_session` with `HttpOnly; Secure; SameSite=Lax; Path=/` and a
   seven-day lifetime. Registration alone does not log in.
3. `new WebSocket(url)` sends the eligible cookie automatically. JavaScript
   neither reads the HttpOnly token nor sets a Cookie/Authorization header.
   There is no WebSocket `credentials` option and no token in the URL.
4. `GET /api/v1/auth/me` returns the public user or `401`; use it to check login
   state. `POST /api/v1/auth/logout` ends the current session and returns `204`.

The backend accepts only exact browser origins in `WEBSOCKET_ALLOWED_ORIGINS`.
Defaults are the two HTTP Vite origins above. HTTPS origins must be explicitly
configured before starting the backend; the browser supplies `Origin` itself.

**Browser setup matters:** Compose currently exposes plain HTTP, the login
cookie is Secure, and Vite currently has no API/WebSocket proxy. The backend
also has no HTTP CORS middleware. The development URL describes the transport;
it is not a guarantee that cross-origin `fetch` login and Secure cookies work
over plain HTTP in every browser. Use trusted local HTTPS and a same-origin API
proxy for the React application, or the backend-only HTTPS recipe below for
verification. `credentials: "include"` alone does not configure HTTP CORS.
Do not weaken the cookie or edit it manually to make the demo work.

## Exact application messages

Frames are JSON **text**. IDs are database user IDs encoded as JSON numbers;
`online` is a JSON boolean. These are the only application message types emitted
by `/ws`. There is no welcome, acknowledgement, error JSON, subscription command,
client heartbeat, echo, or client-triggered broadcast. Text and binary input
frames are ignored. Protocol-level ping/pong is handled by the transport.

### Snapshot (first application frame on every connection)

```json
{"type":"presence_snapshot","data":{"online_user_ids":[7,12]}}
```

Schema: `{ "type": "presence_snapshot", "data": { "online_user_ids": number[] } }`.
An empty result is `{"type":"presence_snapshot","data":{"online_user_ids":[]}}`.

Replace the entire online-friends set; do not merge snapshots. IDs belong only
to accepted, non-deleted friends who currently have at least one registered
socket. Pending, declined, blocked, unrelated, and deleted friends are excluded.
There is no self-status entry, friend name, offline list, timestamp, or sequence
number. Treat the array as a set; ordering has no UI meaning.

For a known accepted friend, absence means offline **only while this connection
has received a snapshot and remains connected**. The snapshot is not the friend
roster: an absent ID could also be a removed friendship. Obtain names and the
roster separately; there is currently no friends-list or friendship-acceptance
HTTP route. A temporary view may use the two demo accounts' IDs and names.
Do not use the database profile `is_online`/`last_seen_at` fields: this transport
does not update them.

Snapshots can recur on the same connection. Friendship IDs are refreshed every
five seconds, plus queue/database time; a changed friend set triggers a replacement
snapshot. An unchanged friend set emits nothing. All recipient tabs receive
their own private snapshot. `open` alone does not mean presence is synchronized.

### Online/offline update (after the initial snapshot)

```json
{"type":"presence","data":{"user_id":7,"online":true}}
```

```json
{"type":"presence","data":{"user_id":7,"online":false}}
```

Schema: `{ "type": "presence", "data": { "user_id": number, "online": boolean } }`.
Add the ID for `true`; remove it for `false`. These are idempotent state
assignments, not counters. Duplicate states can occur after retries; very rapid
disconnect/reconnect transitions may be coalesced to the current state.

The first registered socket schedules online. Further tabs/devices do not
schedule another online transition. Removing the final socket schedules offline.
Delivery goes to every ready socket of accepted, non-deleted friends selected
by the database lookup, with each recipient session checked before sending.
It is not a global broadcast. Snapshots and updates share a serialized dispatcher,
so a change during snapshot delivery is processed afterward. There is no event
replay across connections: a reconnect starts with a fresh snapshot.

## Disconnect, authentication failures, and recovery

On any local socket loss, immediately display **Unknown / Reconnecting** for
friends and discard or mark the cached set stale. Do not infer that all friends
went offline, and do not keep displaying cached IDs as definitely online.
Closing this client's socket changes only this user's connection count; another
tab or independent login can keep the user online. Unexpected network loss is
observed when the transport detects it, not necessarily when Wi-Fi is switched
off. Background tabs remain online while connected; this is not activity/idle
tracking.

| Situation | Server behavior / client action |
| --- | --- |
| Invalid/missing cookie or disallowed Origin at handshake | Denied before acceptance; browsers normally report an upgrade failure/`1006`, not the server's internal `1008`. Check `/me` and Origin configuration. |
| Session expires, is revoked, or its account is deleted after connection | Close `1008`, detected before an outbound frame or by a ten-second session check, plus bounded database/lock/close time. Stop automatic retries and require a valid login. |
| Successful HTTP logout | Immediately removes all sockets for that login token after commit and closes with `1008`; independent sessions remain. Stop the client before logout and on unmount. |
| Database failure during handshake/session validation | Handshake denial, or `1011` on an accepted socket; protected frames are withheld. Retry with backoff. |
| Initial snapshot lookup/send fails or initialization times out | Socket removed and closed (normally `1011`); no readiness until a snapshot. Reconnect. |
| Transient presence recipient lookup fails | Server retries current state after 1, 2, 4, 8, 16, then at most 30 seconds; offline transitions are retained. Delivery can be delayed. |
| Transient friendship refresh lookup fails | Retry at the next refresh; the transport can remain open. This does not prevent independent session validation from closing on a database outage. |
| Non-transient presence lookup error | Logged without endless retries; fix the backend error and reconnect to resynchronize. |
| Initialization capacity exceeded | Denied before acceptance (internal `1013`, usually browser `1006`); back off. Limits: 64 pending globally, four per user, excluding ready sockets. |
| Server restart / network interruption | No durable presence state or replay. Retry and replace state from the new snapshot. |

No client can infer the cause of every `1006`. Recheck `/me` through the working
HTTP API: `401` means log in again; a network/5xx failure is retryable. Use
exponential backoff with jitter (roughly one second up to 30 seconds), one socket
per mounted provider, and one retry timer. Reset the retry delay only after a
snapshot, not on `open`. Cancel timers and close the socket on logout/unmount.
Ignore unknown message types for forward compatibility.

## Minimal framework-independent JavaScript

This example keeps transport state separate from friend status and checks the
session before each connection attempt. `apiBase` must point to a working
same-origin API (or an API with credentialed CORS configured). Adapt `render`
to React state; a known friend is online iff `state === "ready"` and its numeric
ID belongs to `onlineIds`. Other connection states mean unknown.

```js
function watchPresence({ wsUrl, apiBase, render }) {
  let socket, timer, snapshotTimer, stopped = false, attempts = 0;
  let onlineIds = new Set();
  const requests = new AbortController();
  const publish = (state) => render({ state, onlineIds: new Set(onlineIds) });
  const unknown = (state) => { onlineIds.clear(); publish(state); };
  const retry = () => {
    if (stopped) return;
    unknown("reconnecting");
    const cap = Math.min(30000, 1000 * 2 ** Math.min(attempts++, 5));
    timer = setTimeout(connect, cap * (0.5 + Math.random() / 2));
  };
  async function connect() {
    if (stopped) return;
    unknown("connecting");
    try {
      const me = await fetch(new URL("/api/v1/auth/me", apiBase), {
        credentials: "include", signal: requests.signal,
      });
      if (stopped) return;
      if (me.status === 401) { stopped = true; unknown("login-required"); return; }
      if (!me.ok) { retry(); return; }
      socket = new WebSocket(wsUrl);
    } catch {
      retry();
      return;
    }
    const current = socket;
    let ready = false;
    snapshotTimer = setTimeout(() => current.close(), 30000);
    current.onmessage = ({ data }) => {
      if (stopped || current !== socket) return;
      const message = JSON.parse(data);
      if (message.type === "presence_snapshot") {
        onlineIds = new Set(message.data.online_user_ids);
        ready = true;
        attempts = 0;
        clearTimeout(snapshotTimer);
      } else if (message.type === "presence" && ready) {
        const { user_id, online } = message.data;
        if (online) onlineIds.add(user_id);
        else onlineIds.delete(user_id);
      } else return;
      publish("ready");
    };
    // Connection errors also produce close; schedule retries only there.
    current.onclose = ({ code }) => {
      clearTimeout(snapshotTimer);
      if (stopped || current !== socket) return;
      if (code === 1008) { stopped = true; unknown("login-required"); }
      else retry();
    };
  }
  void connect();
  return function stop() {
    stopped = true;
    requests.abort();
    clearTimeout(timer);
    clearTimeout(snapshotTimer);
    socket?.close();
    unknown("stopped");
  };
}

// In the HTTPS backend-only demo, paste this in the /docs page console.
const wsUrl = new URL("/ws", location.origin);
wsUrl.protocol = location.protocol === "https:" ? "wss:" : "ws:";
const stopPresence = watchPresence({
  wsUrl, apiBase: location.origin,
  render: ({ state, onlineIds }) => console.log(state, [...onlineIds]),
});
// Call stopPresence() on logout/unmount; start a new watcher after login.
```

With separate development ports, pass the backend WebSocket URL explicitly;
deriving it from the Vite page would otherwise target port 5173. Investigate
repeated upgrade failures with `/me` returning 200: usually the wrong URL,
Origin, certificate, or cookie policy. Backoff does not repair configuration.

## Reproducible two-account browser test (no frontend changes)

Use a migrated **development** PostgreSQL database, the backend virtualenv, and
a browser-trusted local certificate covering `localhost`. If using `mkcert`,
generate a local certificate outside the repo with
`mkcert -cert-file /tmp/myplaylist-local.pem -key-file /tmp/myplaylist-local-key.pem localhost`
after installing/trusting its local CA. Never commit private keys. TLS is an
external development prerequisite; this repository does not provision it.

1. From `backend/`, export your development `DATABASE_URL`, migrate with
   `.venv/bin/alembic upgrade head`, then start one backend:

   ```sh
   WEBSOCKET_ALLOWED_ORIGINS=https://localhost:8443 \
     .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8443 \
     --ssl-certfile /tmp/myplaylist-local.pem \
     --ssl-keyfile /tmp/myplaylist-local-key.pem
   ```

2. Open `https://localhost:8443/docs` in two **separate browser profiles** (A
   and B), so cookies are independent. In Swagger's **Try it out**, register
   `alex@example.test` / `Alex` and `sam@example.test` / `Sam`, each with a local
   password of at least eight characters. Log in as Alex in A and Sam in B.
   Verify `/api/v1/auth/me` returns the correct, distinct IDs. Already-created
   accounts can simply log in. Swagger requests are same-origin; no CORS or
   JavaScript access to the cookie is needed.
3. Make those accounts accepted friends. There is no acceptance HTTP route;
   in a second terminal using the same development database, run from `backend/`:

   ```sh
   .venv/bin/python - <<'PY'
   from sqlalchemy import select
   from app.db import SessionLocal
   from app.db.models import User
   from app.db.friendships import list_friends, send_friend_request

   with SessionLocal.begin() as session:
       alex = session.scalars(select(User).where(User.email == "alex@example.test")).one()
       sam = session.scalars(select(User).where(User.email == "sam@example.test")).one()
       send_friend_request(session, alex.id, sam.id)
       send_friend_request(session, sam.id, alex.id)  # reciprocal request accepts
       assert sam.id in [friend.id for friend in list_friends(session, alex.id)]
       print({"Alex": alex.id, "Sam": sam.id})
   PY
   ```

   Use fresh demo accounts; the helper deliberately does not override a blocked
   friendship. The transaction must commit before presence can observe it.
4. Paste the JavaScript example into A's `/docs` console: expect `ready []`.
   Paste it into B: B's snapshot contains Alex's ID; A receives Sam's ID online.
   In DevTools Network → WS → Messages, inspect the exact JSON frames.
5. Open a second B tab in the **same profile**, visit `/docs`, and start another
   watcher. It receives its own snapshot; A must not receive another online
   transition just because B opened another tab.
6. Run `stopPresence()` in the first B tab. Sam stays online in A. Stop the
   second B watcher: A receives Sam offline. Restart the watcher in B: B gets
   a fresh snapshot and A receives Sam online without reloading.
7. With both B tabs connected again, stop their watchers and execute HTTP
   logout in B. Alternatively, leave them running once to observe server-driven
   `1008` closure and `login-required`. A receives Sam offline after the last
   socket is removed. A's independent login remains valid. Logging in again
   requires starting a new watcher.
8. To verify isolation, stop both watchers, use fresh demo accounts without step 3, and
   repeat connect/disconnect: neither account receives the other's presence.
   Pending friendship alone must also be invisible. The automated suite covers
   both directions, blocked/declined/deleted friends, and reconnect races.

For connection-loss UI testing, interrupt the backend while both watchers run:
both must switch to reconnecting/unknown when closure is detected. Restart the
same backend and verify a fresh snapshot restores state. Browser offline mode
alone may not immediately terminate an already-open WebSocket.
