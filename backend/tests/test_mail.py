"""SMTP transport uses secure modes, bounded waits and sanitized failures."""

import smtplib

import pytest

from app.mail import MailDeliveryError, SMTPMailer, SMTPSettings


class FakeSMTP:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def starttls(self, **kwargs):
        self.calls.append(("starttls", kwargs))

    def login(self, username, password):
        self.calls.append(("login", username, password))

    def send_message(self, message):
        self.calls.append(("send_message", message))


@pytest.mark.parametrize("security,port", [("starttls", "587"), ("ssl", "465")])
def test_secure_smtp_modes_use_timeout_auth_and_safe_confirmation(monkeypatch, security, port):
    fake = FakeSMTP()
    constructor = []

    def make_smtp(host, actual_port, **kwargs):
        constructor.append((host, actual_port, kwargs))
        return fake

    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", port)
    monkeypatch.setenv("SMTP_FROM", "no-reply@example.test")
    monkeypatch.setenv("SMTP_SECURITY", security)
    monkeypatch.setenv("SMTP_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("SMTP_USERNAME", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-secret")
    monkeypatch.setattr(smtplib, "SMTP_SSL" if security == "ssl" else "SMTP", make_smtp)

    SMTPMailer().send_export_confirmation("alice@example.test")

    assert constructor[0][0:2] == ("smtp.example.test", int(port))
    assert constructor[0][2]["timeout"] == 2.5
    if security == "starttls":
        assert fake.calls[0][0] == "starttls"
    else:
        assert "context" in constructor[0][2]
    assert ("login", "smtp-user", "smtp-secret") in fake.calls
    message = fake.calls[-1][1]
    assert message["To"] == "alice@example.test"
    assert "download" in message.get_content().lower()
    assert "smtp-secret" not in message.as_string()


def test_local_mailpit_allows_plain_smtp_without_credentials(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "mailpit")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_FROM", "no-reply@myplaylist.local")
    monkeypatch.setenv("SMTP_SECURITY", "none")
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    assert SMTPSettings.from_environment().security == "none"


def test_missing_smtp_host_fails_without_revealing_configuration(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    with pytest.raises(MailDeliveryError) as captured:
        SMTPSettings.from_environment()
    assert str(captured.value) == "Email delivery is unavailable"


@pytest.mark.parametrize("host,security,username,password", [
    ("remote.example.test", "none", "", ""),
    ("mailpit", "none", "user", "password"),
    ("smtp.example.test", "starttls", "user", ""),
])
def test_insecure_or_incomplete_configuration_fails_closed(monkeypatch, host, security, username, password):
    monkeypatch.setenv("SMTP_HOST", host)
    monkeypatch.setenv("SMTP_FROM", "no-reply@example.test")
    monkeypatch.setenv("SMTP_SECURITY", security)
    monkeypatch.setenv("SMTP_USERNAME", username)
    monkeypatch.setenv("SMTP_PASSWORD", password)
    with pytest.raises(MailDeliveryError, match="unavailable"):
        SMTPSettings.from_environment()


def test_smtp_failure_is_sanitized(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "no-reply@example.test")
    monkeypatch.setenv("SMTP_SECURITY", "starttls")
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    def fail(*_args, **_kwargs):
        raise smtplib.SMTPException("secret provider response")

    monkeypatch.setattr(smtplib, "SMTP", fail)
    with pytest.raises(MailDeliveryError) as captured:
        SMTPMailer().send_export_confirmation("alice@example.test")
    assert "secret provider response" not in str(captured.value)
