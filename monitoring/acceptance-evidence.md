# Issue #59 monitoring acceptance evidence

Live test: 2026-11-23, against `origin/main` commit `89171bad4ac7f9cf6268a46e53ff9dd2767614b9` plus the monitoring documentation and read-only checker in this worktree.

The test used disposable Compose project `ft59accept7a00f87c`, with fresh credentials and project-prefixed volumes. Only loopback host ports were published: Caddy 18080/18443, Postgres 15432, Grafana 13000, and Prometheus 19090. The backend and frontend had no published ports. Existing shared containers were not stopped or changed.

A disposable copy of `docker-compose.yml` at the worktree root remapped those five ports; `docker compose config --format json` confirmed the exact published ports, project-prefixed volumes, and bind mounts confined to this worktree before startup. The copy and disposable `.env` were removed after the test. The project's containers, network, five named volumes, anonymous frontend volume, and two built images were also removed by explicit project/name; shared resources remain in place.

| Requirement | Observed evidence | Result |
| --- | --- | --- |
| Prometheus collects application metrics | All six disposable services started; Postgres was healthy. The backend `/health` response was `{"status":"ok","database":"ok"}`. Its `/metrics` response contained the HTTP request counter and WebSocket gauge. `monitoring/check_readonly.py` reported `up{job="myplaylist-backend"} == 1` and found HTTP request, duration bucket, and active WebSocket series. | Pass |
| Custom Grafana dashboard shows live data | HTTPS registration returned 201, login returned 200, and 30 authenticated `/api/v1/auth/me` requests all returned 200. Grafana's datasource proxy evaluated the dashboard's own expressions: request rate `0.02034830282100173` requests/s, p95 latency `0.004750000000000001` seconds, and active WebSockets `0` at that instant. A separate authenticated WebSocket handshake returned 101 and Prometheus observed the gauge rise to `1`. Headless Chrome displayed plotted request rate, p95 latency, and WebSocket history on the provisioned four-panel dashboard after the Grafana restart. The 5xx panel showed **No data** because no 5xx response was generated. [Dashboard screenshot](evidence/issue59-dashboard.png). | Pass |
| Backend-unavailable alert changes state and recovers | Grafana's rules API reported the sequence below, with rule health `ok` throughout. The backend was stopped and restored **only** in the disposable project. | Pass |
| Grafana access is secured | Grafana and Prometheus were bound to `127.0.0.1`. The dashboard API returned 401 with no credentials and with an incorrect password. Login with the disposable admin password returned 200; the authenticated API returned the provisioned datasource, dashboard, and alert rule. | Pass |
| Provisioning survives restart | After `docker compose -p ft59accept7a00f87c -f .issue59-acceptance.yml restart grafana`, the read-only checker passed again: unauthenticated API access was denied and the Prometheus datasource, four-panel dashboard, and backend alert rule were present. The dashboard screenshot was captured after this restart. | Pass |

Alert lifecycle, UTC:

| Time | Prometheus `up` | Grafana rule / alert |
| --- | ---: | --- |
| 22:46:37, before stop | 1 | inactive / Normal |
| 22:46:42, after stop | 0 | inactive / Normal |
| 22:47:03 | 0 | pending / Pending |
| 22:49:03 | 0 | firing / Alerting |
| 22:49:08, after restore | 1 | firing / Alerting |
| 22:49:34 | 1 | inactive / Normal |

The test establishes local, authenticated Grafana access and an in-app alert rule. External notification delivery was not tested or configured; it is outside issue #59's stated acceptance criteria.
