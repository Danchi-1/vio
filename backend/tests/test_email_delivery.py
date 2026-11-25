from dataclasses import dataclass

import pytest

from vio_backend.email_delivery import (
    EmailDeliveryUnavailable,
    NullEmailSender,
    SmtpEmailSender,
    build_email_sender,
)


@dataclass
class FakeSettings:
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_address: str | None = None


@pytest.mark.asyncio
async def test_null_sender_fails_closed_instead_of_pretending_to_send():
    with pytest.raises(EmailDeliveryUnavailable):
        await NullEmailSender().send(to_address="student@student.funaab.edu.ng", subject="s", body="b")


def test_build_email_sender_returns_null_sender_when_unconfigured():
    assert isinstance(build_email_sender(FakeSettings()), NullEmailSender)


def test_build_email_sender_returns_null_sender_when_partially_configured():
    settings = FakeSettings(smtp_host="smtp.gmail.com", smtp_username="me@gmail.com")
    assert isinstance(build_email_sender(settings), NullEmailSender)


def test_build_email_sender_returns_smtp_sender_when_fully_configured():
    settings = FakeSettings(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_username="me@gmail.com",
        smtp_password="app-password",
        smtp_from_address="me@gmail.com",
    )
    sender = build_email_sender(settings)
    assert isinstance(sender, SmtpEmailSender)
    assert sender.host == "smtp.gmail.com"
