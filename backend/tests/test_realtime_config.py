import pytest

from app.realtime.config import allowed_websocket_origins


def test_local_defaults(monkeypatch):
    monkeypatch.delenv("WEBSOCKET_ALLOWED_ORIGINS", raising=False)
    assert allowed_websocket_origins() == {"http://localhost:5173", "http://127.0.0.1:5173"}


def test_explicit_origins_replace_defaults_and_trim_whitespace(monkeypatch):
    monkeypatch.setenv("WEBSOCKET_ALLOWED_ORIGINS", " https://music.example, https://music.example:8443,https://music.example ")
    assert allowed_websocket_origins() == {"https://music.example", "https://music.example:8443"}


def test_empty_setting_disables_websockets(monkeypatch):
    monkeypatch.setenv("WEBSOCKET_ALLOWED_ORIGINS", "")
    assert allowed_websocket_origins() == set()


@pytest.mark.parametrize("origin", ["*", "null", "https://*.example", "wss://music.example", "https://music.example/path", "https://music.example/", "https://music.example?x=1", "https://music.example#fragment", "https://user:pass@music.example", "https://music.example:99999", "https://music.example:abc", "https://music. example", "https://"])
def test_invalid_configuration_fails_closed(monkeypatch, origin):
    monkeypatch.setenv("WEBSOCKET_ALLOWED_ORIGINS", origin)
    with pytest.raises(ValueError, match="WEBSOCKET_ALLOWED_ORIGINS"):
        allowed_websocket_origins()
