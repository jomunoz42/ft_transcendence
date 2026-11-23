#!/usr/bin/env python3
"""Read-only checks for a running, isolated monitoring stack."""

import argparse
import base64
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def get_json(url, authorization=None):
    headers = {"Authorization": authorization} if authorization else {}
    with urlopen(Request(url, headers=headers), timeout=10) as response:
        return json.load(response)


def check(condition, message):
    if not condition:
        raise ValueError(message)
    print(f"PASS {message}")


def prometheus_query(base_url, expression):
    url = f"{base_url}/api/v1/query?{urlencode({'query': expression})}"
    payload = get_json(url)
    check(payload.get("status") == "success", f"Prometheus query succeeded: {expression}")
    data = payload.get("data", {})
    check(data.get("resultType") == "vector", f"Prometheus returned a vector: {expression}")
    result = data.get("result")
    if not isinstance(result, list):
        raise ValueError(f"Prometheus returned no vector results for {expression}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prometheus-url", default="http://127.0.0.1:9090")
    parser.add_argument("--grafana-url", default="http://127.0.0.1:3000")
    args = parser.parse_args()
    prometheus = args.prometheus_url.rstrip("/")
    grafana = args.grafana_url.rstrip("/")

    with urlopen(f"{prometheus}/-/ready", timeout=10) as response:
        check(response.status == 200, "Prometheus is ready")

    up = prometheus_query(prometheus, 'up{job="myplaylist-backend"}')
    up_value = up[0].get("value") if len(up) == 1 else None
    check(isinstance(up_value, list) and len(up_value) > 1 and up_value[1] == "1",
          "backend scrape target is up")
    for metric in (
        "myplaylist_http_requests_total",
        "myplaylist_http_request_duration_seconds_bucket",
        "myplaylist_ws_active_connections",
    ):
        check(bool(prometheus_query(prometheus, metric)), f"Prometheus has {metric}")

    try:
        get_json(f"{grafana}/api/search")
    except HTTPError as error:
        check(error.code == 401, "Grafana dashboard API requires authentication")
    else:
        raise ValueError("Grafana dashboard API allowed unauthenticated access")

    password = os.environ.get("GRAFANA_ADMIN_PASSWORD")
    if not password:
        raise ValueError("set GRAFANA_ADMIN_PASSWORD to check provisioned resources")

    user = os.environ.get("GRAFANA_ADMIN_USER", "admin")
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    authorization = f"Basic {token}"
    datasource = get_json(f"{grafana}/api/datasources/uid/prometheus", authorization)
    check(datasource.get("uid") == "prometheus", "Prometheus datasource is provisioned")

    dashboard = get_json(f"{grafana}/api/dashboards/uid/myplaylist-overview", authorization)
    check(dashboard.get("dashboard", {}).get("uid") == "myplaylist-overview" and
          len(dashboard.get("dashboard", {}).get("panels", [])) == 4,
          "four-panel backend dashboard is provisioned")

    alert = get_json(f"{grafana}/api/v1/provisioning/alert-rules/myplaylist-backend-down",
                     authorization)
    check(alert.get("uid") == "myplaylist-backend-down", "backend alert rule is provisioned")


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError, ValueError, OSError) as error:
        print(f"FAIL {error}", file=sys.stderr)
        sys.exit(1)
