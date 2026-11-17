"""Tests for HTTP and WebSocket Prometheus instrumentation."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from app.main import app
from app.monitoring.metrics import (
    HTTP_DURATION,
    HTTP_REQUESTS,
    WS_ACTIVE_CONNECTIONS,
    WS_CONNECTIONS_TOTAL,
    WS_DISCONNECTIONS_TOTAL,
)
from app.monitoring.middleware import PrometheusMiddleware
from app.realtime.manager import ConnectionManager


def test_http_metrics_record_requests_and_duration():
    test_app = FastAPI()
    test_app.add_middleware(PrometheusMiddleware)

    @test_app.get("/monitoring-test")
    def endpoint():
        return {"ok": True}

    requests = HTTP_REQUESTS.labels(
        method="GET", route="/monitoring-test", status="200"
    )
    duration = HTTP_DURATION.labels(
        method="GET", route="/monitoring-test"
    )

    before_requests = requests._value.get()
    before_observations = duration._sum.get()

    with TestClient(test_app) as client:
        response = client.get("/monitoring-test")

    assert response.status_code == 200
    assert requests._value.get() == before_requests + 1
    assert duration._sum.get() >= before_observations


def test_metrics_endpoint_exposes_prometheus_data():
    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "myplaylist_http_requests_total" in response.text
    assert "myplaylist_http_request_duration_seconds" in response.text
    assert "myplaylist_ws_active_connections" in response.text
    assert "myplaylist_ws_connections_total" in response.text
    assert "myplaylist_ws_disconnections_total" in response.text
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.anyio
async def test_websocket_metrics_track_connections_and_disconnections(monkeypatch):
    manager = ConnectionManager()
    monkeypatch.setattr(
        manager, "check_session", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(manager, "schedule_presence", lambda user_id: None)

    socket = MagicMock(spec=WebSocket)

    before_active = WS_ACTIVE_CONNECTIONS._value.get()
    before_connected = WS_CONNECTIONS_TOTAL._value.get()
    before_disconnected = WS_DISCONNECTIONS_TOTAL._value.get()

    await manager.connect(socket, 12345)

    assert WS_ACTIVE_CONNECTIONS._value.get() == before_active + 1
    assert WS_CONNECTIONS_TOTAL._value.get() == before_connected + 1

    manager.disconnect(socket, 12345)

    assert WS_ACTIVE_CONNECTIONS._value.get() == before_active
    assert WS_DISCONNECTIONS_TOTAL._value.get() == before_disconnected + 1

    manager.disconnect(socket, 12345)

    assert WS_ACTIVE_CONNECTIONS._value.get() == before_active
    assert WS_DISCONNECTIONS_TOTAL._value.get() == before_disconnected + 1
