# Monitoring

MyPlaylist uses Prometheus and Grafana to monitor backend availability, HTTP performance, and WebSocket activity.

Prometheus collects metrics exposed by the backend. Grafana visualizes these metrics and evaluates alert rules. Configuration is stored in version-controlled files to support reproducible deployments.

## Components

| Component | Purpose | Local URL |
| --- | --- | --- |
| Prometheus | Metrics collection and querying | http://localhost:9090 |
| Grafana | Dashboards and alerting | http://localhost:3000 |
| Backend | Application metrics | http://localhost:8000/metrics |

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

## Validation

Verify backend health:

```bash
curl -fsS http://localhost:8000/health
```

Verify Prometheus readiness:

```bash
curl -fsS http://localhost:9090/-/ready
```

Check whether Prometheus can scrape the backend:

```bash
curl -fsS -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=up{job="myplaylist-backend"}'
```

A result value of `"1"` indicates a successful scrape.

To validate the alert lifecycle in a local test environment:

1. Keep Grafana and Prometheus running.
2. Stop the backend using `docker-compose stop backend`.
3. Wait for the alert to transition from Normal to Pending and then Firing.
4. Restore the backend using `docker-compose up -d backend`.
5. Verify backend health and confirm the alert returns to Normal.

This procedure temporarily interrupts the application and should only be performed in an appropriate test environment.

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
