"""Exercise query-free access logging through a real Uvicorn worker."""

from contextlib import contextmanager
import http.client
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from urllib.parse import urlencode

from websockets.sync.client import connect
from websockets.exceptions import InvalidStatus

import pytest


BACKEND = Path(__file__).resolve().parents[1]


def request(port: int, method: str, path: str) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


@contextmanager
def uvicorn_worker(log_path: Path, http_impl: str):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(BACKEND), str(BACKEND / "tests")))
    with log_path.open("w+") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "access_log_app:app", "--host", "127.0.0.1", "--port", str(port), "--http", http_impl],
            cwd=BACKEND,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    if request(port, "GET", "/ready")[0] == 200:
                        yield port
                        return
                except OSError:
                    time.sleep(0.05)
            raise AssertionError("Uvicorn probe did not start")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.mark.parametrize("http_impl", ["h11", "httptools"])
def test_real_uvicorn_omits_entire_query_and_keeps_access_details(tmp_path, http_impl):
    log_path = tmp_path / "uvicorn.log"
    code = "synthetic/code+value"
    state = "synthetic state&value"
    callback = "/api/v1/auth/42/callback"
    google_callback = "/api/v1/auth/google/callback"
    query = urlencode({"code": code, "state": state, "extra": "one&two", "scope": "email profile"})

    with uvicorn_worker(log_path, http_impl) as port:
        assert request(port, "GET", f"{callback}?{query}") == (200, b"accepted")
        assert request(port, "GET", f"{callback}?{urlencode({'code': code, 'state': 'wrong', 'error': 'access_denied'})}")[0] == 400
        assert request(port, "GET", f"{google_callback}?{query}")[0] == 200
        assert request(port, "GET", "/ordinary?search=synthetic+term")[0] == 200
        assert request(port, "POST", "/ordinary?filter=synthetic%2Ffilter")[0] == 201
        assert request(port, "GET", "/raise?code=synthetic-exception-code")[0] == 500
        with connect(f"ws://127.0.0.1:{port}/ws?token=synthetic-ws-token", open_timeout=3):
            pass
        with pytest.raises(InvalidStatus):
            with connect(f"ws://127.0.0.1:{port}/ws?token=synthetic-rejected-ws-token&state=synthetic%2Bstate", open_timeout=3):
                pass

    logs = log_path.read_text()
    for request_line, status in (
        (f"GET {callback} HTTP/1.1", 200),
        (f"GET {callback} HTTP/1.1", 400),
        (f"GET {google_callback} HTTP/1.1", 200),
        ("GET /ordinary HTTP/1.1", 200),
        ("POST /ordinary HTTP/1.1", 201),
        ("GET /raise HTTP/1.1", 500),
    ):
        assert re.search(rf'127\.0\.0\.1:\d+ - "{re.escape(request_line)}" {status}', logs)
    assert '"WebSocket /ws" [accepted]' in logs
    assert '"WebSocket /ws" 403' in logs
    assert "synthetic handler failure" in logs
    assert "?" not in logs
    for marker in (code, state, "synthetic%2Fcode%2Bvalue", "synthetic+state%26value", "synthetic-ws-token", "synthetic-rejected-ws-token"):
        assert marker not in logs
