"""Small SMTP transport for account-operation emails.

Configuration is read when a message is sent, so a missing mail setup does not
prevent unrelated API routes from starting. Errors never include SMTP details.
"""

import os
import smtplib
import ssl
import math
from dataclasses import dataclass
from email.errors import MessageError
from email.message import EmailMessage


class MailDeliveryError(Exception):
    """The requested message could not be delivered to the SMTP server."""


@dataclass(frozen=True)
class SMTPSettings:
    host: str
    port: int
    sender: str
    security: str
    timeout: float
    username: str | None
    password: str | None

    @classmethod
    def from_environment(cls) -> "SMTPSettings":
        try:
            host = os.environ["SMTP_HOST"].strip()
            sender = os.environ["SMTP_FROM"].strip()
            port = int(os.environ.get("SMTP_PORT", "587"))
            timeout = float(os.environ.get("SMTP_TIMEOUT_SECONDS", "10"))
            security = os.environ.get("SMTP_SECURITY", "starttls").strip().lower()
            username = os.environ.get("SMTP_USERNAME") or None
            password = os.environ.get("SMTP_PASSWORD") or None
        except (KeyError, ValueError):
            raise MailDeliveryError("Email delivery is unavailable") from None

        if (
            not host or not sender or not 1 <= port <= 65535 or timeout <= 0 or not math.isfinite(timeout)
            or security not in {"starttls", "ssl", "none"}
            or bool(username) != bool(password)
            or (security == "none" and (username is not None or host not in {"mailpit", "localhost", "127.0.0.1"}))
        ):
            raise MailDeliveryError("Email delivery is unavailable")
        return cls(host, port, sender, security, timeout, username, password)


class SMTPMailer:
    def send(self, recipient: str, subject: str, body: str) -> None:
        """Send one plain-text message; callers choose the operation-specific text."""
        settings = SMTPSettings.from_environment()
        try:
            message = EmailMessage()
            message["From"] = settings.sender
            message["To"] = recipient
            message["Subject"] = subject
            message.set_content(body)
            if settings.security == "ssl":
                connection = smtplib.SMTP_SSL(
                    settings.host, settings.port, timeout=settings.timeout,
                    context=ssl.create_default_context(),
                )
            else:
                connection = smtplib.SMTP(settings.host, settings.port, timeout=settings.timeout)
            with connection as smtp:
                if settings.security == "starttls":
                    smtp.starttls(context=ssl.create_default_context())
                if settings.username is not None:
                    smtp.login(settings.username, settings.password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException, ssl.SSLError, ValueError, UnicodeError, MessageError):
            raise MailDeliveryError("Email could not be sent") from None

    def send_export_confirmation(self, recipient: str) -> None:
        self.send(
            recipient,
            "Your MyPlaylist data export",
            "A download of your MyPlaylist data was requested from your signed-in account.\n"
            "If this was not you, contact the project team.\n",
        )


def get_mailer() -> SMTPMailer:
    return SMTPMailer()
