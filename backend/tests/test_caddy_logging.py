"""Verify Caddy runtime errors cannot log callback query strings."""

import json
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import time
from urllib import error, request
from uuid import uuid4

import pytest


CADDYFILE = Path(__file__).resolve().parents[2] / "Caddyfile"


def test_caddy_upstream_failure_logs_path_without_query(tmp_path):
    if not shutil.which("docker") or subprocess.run(["docker", "info"], capture_output=True).returncode:
        pytest.skip("Docker is unavailable for the Caddy integration test")

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    project = f"ft_sensitive_caddy_{uuid4().hex[:12]}"
    compose_file = tmp_path / "compose.yml"
    compose_file.write_text(
        "services:\n"
        "  caddy:\n"
        "    image: caddy:2-alpine\n"
        f"    ports: [\"127.0.0.1:{port}:443\"]\n"
        f"    volumes: [{json.dumps(str(CADDYFILE) + ':/etc/caddy/Caddyfile:ro')}]\n"
        "    tmpfs: [/data, /config]\n"
    )
    compose = ["docker", "compose", "-p", project, "-f", str(compose_file)]

    def run(*args):
        return subprocess.run(compose + list(args), capture_output=True, text=True)

    try:
        assert run("up", "-d").returncode == 0, "isolated Caddy did not start"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            cert = subprocess.run(
                compose + ["exec", "-T", "caddy", "cat", "/data/caddy/pki/authorities/local/root.crt"],
                capture_output=True,
            )
            if cert.returncode == 0 and cert.stdout:
                break
            time.sleep(0.1)
        else:
            raise AssertionError("isolated Caddy root certificate was unavailable")

        context = ssl.create_default_context(cadata=cert.stdout.decode())
        opener = request.build_opener(request.ProxyHandler({}), request.HTTPSHandler(context=context))
        callback = "/api/v1/auth/42/callback"
        url = f"https://localhost:{port}{callback}?code=synthetic%2Fcode&state=synthetic%2Bstate&extra=one%26two"
        try:
            probe = request.Request(url, headers={
                "Cookie": "oauth_state=synthetic-cookie-value",
                "Authorization": "Bearer synthetic-auth-value",
                "Referer": "https://localhost/previous?code=synthetic-referer-code",
            })
            opener.open(probe, timeout=5)
        except error.HTTPError as response:
            assert response.code == 502
        else:
            raise AssertionError("unavailable backend unexpectedly responded")

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            container_id = run("ps", "-q", "caddy").stdout.strip()
            result = subprocess.run(["docker", "logs", container_id], capture_output=True, text=True)
            assert result.returncode == 0
            logs = result.stdout + result.stderr
            if callback in logs:
                break
            time.sleep(0.1)
        else:
            raise AssertionError("Caddy did not emit the upstream error log")

        events = []
        for line in logs.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        assert any(
            event.get("request", {}).get("uri") == callback
            and event["request"].get("method") == "GET"
            for event in events
        ), "Caddy error log lost the callback path or method"
        assert all(marker not in logs for marker in ("synthetic%2Fcode", "synthetic%2Bstate", "one%26two", "synthetic-cookie-value", "synthetic-auth-value", "synthetic-referer-code")), (
            "Caddy error log contained synthetic request secrets"
        )
    finally:
        assert run("down").returncode == 0, "isolated Caddy cleanup failed"
