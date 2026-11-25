"""Email delivery for one-time student verification codes.

Development/current stage uses Gmail SMTP with an app password (see
docs/DECISIONS.md, 2026-11-10). This is explicitly a provisional choice;
personal Gmail accounts are not built for transactional app email at scale.
Replace SmtpEmailSender's configuration with a dedicated transactional
provider before any real student-facing launch.
"""

import asyncio
from dataclasses import dataclass
from email.message import EmailMessage
import smtplib
import ssl
from typing import Protocol


class EmailSender(Protocol):
    async def send(self, *, to_address: str, subject: str, body: str) -> None: ...


class EmailDeliveryUnavailable(RuntimeError):
    """Raised when no email sender is configured. Callers must fail closed
    rather than pretend the code was sent."""


@dataclass(frozen=True)
class SmtpEmailSender:
    host: str
    port: int
    username: str
    password: str
    from_address: str

    async def send(self, *, to_address: str, subject: str, body: str) -> None:
        await asyncio.to_thread(self._send_sync, to_address, subject, body)

    def _send_sync(self, to_address: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.from_address
        message["To"] = to_address
        message.set_content(body)
        context = ssl.create_default_context()
        with smtplib.SMTP(self.host, self.port, timeout=10) as server:
            server.starttls(context=context)
            server.login(self.username, self.password)
            server.send_message(message)


class NullEmailSender:
    """Used when SMTP is not configured. Raises instead of silently
    pretending to send, consistent with the project's fail-closed principle."""

    async def send(self, *, to_address: str, subject: str, body: str) -> None:
        raise EmailDeliveryUnavailable("SMTP is not configured")


def build_email_sender(settings) -> EmailSender:
    if settings.smtp_host and settings.smtp_username and settings.smtp_password and settings.smtp_from_address:
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_address=settings.smtp_from_address,
        )
    return NullEmailSender()
