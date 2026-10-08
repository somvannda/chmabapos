"""Every account email must render through the shared branded shell.

These are the inline, best-effort account messages (see
``docs/email-notifications-plan.md`` §2). They used to be plain text; this guards
against a regression back to un-branded mail.
"""
from __future__ import annotations

import pytest

from app.email import (
    send_invitation_email,
    send_password_reset_email,
    send_store_ready_email,
    send_verification_email,
    send_welcome_email,
)
from app.services.email_layout import code_block, transactional_email


@pytest.fixture
def captured(monkeypatch) -> list[dict]:
    sent: list[dict] = []

    async def fake_send(recipient, subject, body, **kwargs):
        sent.append({"to": recipient, "subject": subject, "text": body, "html": kwargs.get("html")})
        return True

    monkeypatch.setattr("app.email.send_email", fake_send)
    return sent


@pytest.mark.asyncio
async def test_confirmation_code_email_is_branded(captured) -> None:
    await send_verification_email("owner@example.com", "123456")
    message = captured[-1]
    assert message["subject"] == "Your Chmaba confirmation code"
    assert "<!DOCTYPE html>" in message["html"]
    # The code itself is shown in the branded block and the text fallback.
    assert "123456" in message["html"]
    assert "123456" in message["text"]


@pytest.mark.asyncio
async def test_password_reset_email_is_branded(captured) -> None:
    await send_password_reset_email("owner@example.com", "reset-token")
    message = captured[-1]
    assert message["subject"] == "Reset your Chmaba password"
    assert "<!DOCTYPE html>" in message["html"]
    assert "/reset-password?token=reset-token" in message["html"]
    # A plain-text fallback still carries the link for text-only clients.
    assert "/reset-password?token=reset-token" in message["text"]


@pytest.mark.asyncio
async def test_invitation_email_is_branded(captured) -> None:
    await send_invitation_email("invitee@example.com", "invite-token", "Acme & Sons")
    message = captured[-1]
    assert message["subject"] == "You were invited to Acme & Sons on Chmaba"
    assert "<!DOCTYPE html>" in message["html"]
    # User-supplied company name is escaped, not injected raw.
    assert "Acme &amp; Sons" in message["html"]
    assert "Acme & Sons" not in message["html"]
    assert "/accept-invitation?token=invite-token" in message["html"]


@pytest.mark.asyncio
async def test_welcome_email_is_branded(captured) -> None:
    await send_welcome_email("owner@example.com", "Sokha Chan", "sokha")
    message = captured[-1]
    assert message["subject"] == "Welcome to Chmaba"
    assert "<!DOCTYPE html>" in message["html"]
    assert "Sokha" in message["html"]
    assert "/sokha/setup/company" in message["html"]
    assert "/sokha/setup/company" in message["text"]


@pytest.mark.asyncio
async def test_store_ready_email_is_branded(captured) -> None:
    await send_store_ready_email("owner@example.com", "Sokha Chan", "sokha", "Main <Store>")
    message = captured[-1]
    assert message["subject"] == "Your Chmaba store is ready"
    assert "<!DOCTYPE html>" in message["html"]
    assert "Main &lt;Store&gt;" in message["html"]
    assert "/sokha/catalog" in message["html"]


def test_code_block_renders_the_code() -> None:
    html = code_block("654321")
    assert "654321" in html


def test_transactional_shell_accepts_dollar_in_values() -> None:
    # Amounts such as "$20.00" must not break string.Template substitution.
    html = transactional_email(
        heading="Renew Pro - $20.00 Monthly",
        preview="Your plan ends soon.",
        body="<p>Renew for $20.00 to stay on Pro.</p>",
    )
    assert "<!DOCTYPE html>" in html
    assert "$20.00" in html
