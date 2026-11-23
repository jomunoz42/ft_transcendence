# Monitoring

MyPlaylist uses Prometheus and Grafana to monitor backend availability, HTTP performance, and WebSocket activity.

Prometheus collects metrics exposed by the backend. Grafana visualizes these metrics and evaluates alert rules. Configuration is stored in version-controlled files to support reproducible deployments.

## Components

| Component | Purpose | Local URL |
| --- | --- | --- |
| Prometheus | Metrics collection and querying | http://localhost:9090 |
| Grafana | Dashboards and alerting | http://localhost:3000 |
| Backend | Application metrics | `http://backend:8000/metrics` inside the Compose network |

Prometheus scrapes the backend every 15 seconds. Grafana uses Prometheus as its default datasource.

## Setup

Monitoring services are managed through Docker Compose.

Configure the following variables in the project's `.env` file:

```dotenv
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=replace-with-your-own-password
```

The Grafana administrator password is required. The `.env` file must not be committed to version control.

Start the application and monitoring services from the project root:

```bash
docker-compose up -d
```

Open http://localhost:3000 and sign in with the configured Grafana credentials.

Navigate to **Dashboards > MyPlaylist > MyPlaylist — Backend Overview**.

The Prometheus datasource, Grafana dashboard, and alert rules are provisioned automatically. No manual dashboard creation is required.

## Dashboard

The backend overview dashboard contains four panels:

| Panel | Description |
| --- | --- |
| HTTP requests / second | Total HTTP request rate over a five-minute window |
| HTTP 5xx errors / second | Rate of server-side HTTP errors |
| HTTP p95 latency | Estimated 95th-percentile HTTP request duration |
| Active WebSocket connections | Current number of active WebSocket connections |

The dashboard refreshes every 15 seconds and displays the previous hour by default.

Panels may display **No data** when no matching time series have been observed. For example, the HTTP 5xx panel may be empty when no server errors have occurred.

## Alerting

Grafana provisions a **Backend unavailable** alert that monitors the Prometheus metric:

```promql
up{job="myplaylist-backend"}
```

Prometheus reports `1` when the backend scrape succeeds and `0` when it fails.

| Setting | Value |
| --- | --- |
| Evaluation interval | 30 seconds |
| Firing condition | Scrape result below 1 |
| Pending period | 2 minutes |
| Severity | Warning |

The alert enters **Pending** when a scrape failure is detected. If the condition persists for two minutes, it enters **Firing**. Once successful scraping resumes, it returns to **Normal**.

The rule is available under **Alerting > Alert rules > MyPlaylist > Backend availability**.

The alert is intended for environments where backend availability is expected. Intentional shutdowns during local development may trigger it while Grafana and Prometheus remain operational.

Alert status is visible within Grafana. External notification delivery and automatic service recovery are not configured.

## Acceptance checklist (issue #59)

Run this checklist in a disposable checkout on an isolated host with ports 80,
443, 5432, 3000, and 9090 free. Copy `.env.example` to `.env` in that checkout.
Add a unique `COMPOSE_PROJECT_NAME=ft59-accept-<unique-id>` so its database and
Grafana volumes cannot overlap another deployment. Set a strong, unique
`GRAFANA_ADMIN_PASSWORD`, and update `POSTGRES_PASSWORD` and `DATABASE_URL`
together. The commands below use Docker Compose v2; substitute `docker-compose`
if only v1 is installed. Never use `down -v` or `make db-reset` for this check.
On a busy host, use a disposable copy of `docker-compose.yml` in this checkout
with all published ports remapped to unused loopback ports. Inspect
`docker compose -f <copy> config` before starting it, and add `-f <copy>` to
each Compose command below.

1. **Collect application metrics.** Start the disposable stack with
   `docker compose up -d --build` and confirm all services with
   `docker compose ps`. The backend is internal to Compose: host port 8000 is
   not published, and Caddy does not proxy `/health` or `/metrics`. Check them
   from inside the backend container:

   ```bash
   docker compose exec -T backend python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/health").read().decode())'
   docker compose exec -T backend python -c 'import urllib.request; body=urllib.request.urlopen("http://127.0.0.1:8000/metrics").read().decode(); assert "myplaylist_http_requests_total" in body; print("backend metrics present")'
   ```

   Health should report `"status":"ok"`. After at least two Prometheus
   scrapes (30–45 seconds), run the read-only check below. It checks Prometheus
   readiness, `up{job="myplaylist-backend"} == 1`, the HTTP and WebSocket metric
   series, Grafana API authentication, and provisioned resources. It only makes
   GET requests; it does not change containers or data. Enter the password from
   the disposable `.env` when prompted (it is not saved by the script):

   ```bash
   read -r -s -p 'Grafana admin password: ' GRAFANA_ADMIN_PASSWORD; echo
   export GRAFANA_ADMIN_PASSWORD
   python3 monitoring/check_readonly.py
   unset GRAFANA_ADMIN_PASSWORD
   ```

   The script exits nonzero on a failed check. Its default URLs are
   `http://127.0.0.1:9090` and `http://127.0.0.1:3000`; use `--prometheus-url`
   and `--grafana-url` if the isolated host uses different local ports.

2. **Display live dashboard data.** Sign in at `http://127.0.0.1:3000` with
   the configured admin credentials. Open **Dashboards > MyPlaylist >
   MyPlaylist — Backend Overview**. Make several HTTPS application requests,
   wait two more scrapes, and confirm request rate and p95 latency show recent
   samples. The active WebSocket panel should show zero with no client; open an
   authenticated application tab to observe a connection, then close it and
   observe the count fall. A 5xx series is absent until a server error occurs.

3. **Exercise the availability alert.** In this disposable project only, run
   `docker compose stop backend`. Confirm Prometheus reports `up == 0`, then
   watch **Alerting > Alert rules > MyPlaylist > Backend availability** move
   from Normal to Pending to Firing. Allow approximately three minutes for the
   15-second scrape, 30-second evaluation, and two-minute pending period. Run
   `docker compose up -d backend`, confirm `up == 1`, and wait for the alert
   to return to Normal. Record the observed states and times. This step
   intentionally interrupts the disposable application. Query `up` after each
   change with:

   ```bash
   curl -fsSG http://127.0.0.1:9090/api/v1/query --data-urlencode 'query=up{job="myplaylist-backend"}'
   ```

4. **Check Grafana access.** Confirm an unauthenticated request to
   `http://127.0.0.1:3000/api/search` receives HTTP 401 (the script does this),
   while the configured credentials permit dashboard access. Confirm the
   Grafana and Prometheus ports are bound to `127.0.0.1` in `docker compose ps`.

5. **Check provisioning after restart.** Run `docker compose restart grafana`
   in the disposable project. Once Grafana is ready, rerun the read-only script
   with `GRAFANA_ADMIN_PASSWORD` set as above. Confirm the datasource,
   four-panel dashboard, and alert rule still appear in Grafana. Record these
   results before claiming the module's two points in the root README.

## Configuration

Monitoring configuration is organized as follows:

```text
monitoring/
├── README.md
├── prometheus/
│   └── prometheus.yml
└── grafana/
    ├── dashboards/
    │   └── myplaylist-overview.json
    └── provisioning/
        ├── alerting/
        │   └── backend.yml
        ├── dashboards/
        │   └── dashboards.yml
        └── datasources/
            └── prometheus.yml
```

Grafana loads provisioned alert configuration during startup. After modifying alert provisioning files, restart Grafana:

```bash
docker-compose restart grafana
```

## Troubleshooting

If dashboard panels show no data, verify backend availability and inspect the Prometheus targets at http://localhost:9090/targets.

Inspect service logs when necessary:

```bash
docker-compose logs --tail=50 backend
docker-compose logs --tail=50 prometheus
docker-compose logs --tail=50 grafana
```

A running container does not necessarily indicate a healthy application. Verify the backend health endpoint and Prometheus scrape status before diagnosing Grafana itself.
