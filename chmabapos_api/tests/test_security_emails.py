"""Security notice emails (password changed)."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.email import send_password_changed_email
from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_password_changed_email_is_branded_html(monkeypatch) -> None:
    captured: dict = {}

    async def fake_send(recipient, subject, body, **kwargs):
        captured.update(recipient=recipient, subject=subject, text=body, html=kwargs.get("html"))
        return True

    monkeypatch.setattr("app.email.send_email", fake_send)

    ok = await send_password_changed_email("owner@example.com", "Sokha Chan")
    assert ok is True
    assert captured["recipient"] == "owner@example.com"
    assert captured["subject"] == "Your Chmaba password was changed"
    assert "<!DOCTYPE html>" in captured["html"]
    assert "Sokha" in captured["html"]


@pytest.mark.asyncio
async def test_change_password_sends_security_notice(monkeypatch) -> None:
    sent: list[tuple] = []

    async def fake_notice(recipient, full_name=None):
        sent.append((recipient, full_name))
        return True

    monkeypatch.setattr("app.api.v1.send_password_changed_email", fake_notice)

    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Security Store", "Main", plan="free", email_prefix="security")
            email, company_id = ctx["email"], ctx["company_id"]
            changed = await client.post(
                "/api/v1/auth/change-password",
                headers=ctx["headers"],
                json={"current_password": "strong-password", "new_password": "new-strong-password"},
            )
            assert changed.status_code == 200, changed.text
            assert [entry[0] for entry in sent] == [email]
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
