"""Ops alert when a queued email exhausts its retries."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
from app.services.mailing import MAILING_MAX_ATTEMPTS, send_pending_emails


@pytest.mark.asyncio
async def test_exhausted_send_alerts_platform_admins(monkeypatch) -> None:
    admin_email = f"ops-admin-{uuid.uuid4().hex[:8]}@example.com"
    queued_recipient = f"buyer-{uuid.uuid4().hex[:8]}@example.com"
    alerts: list[tuple[str, str]] = []

    async def fake_send(recipient, subject, body, **kwargs):
        if recipient == admin_email:
            alerts.append((recipient, subject))
            return True, None
        return False, None

    monkeypatch.setattr("app.services.mailing.send_email_with_id", fake_send)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": admin_email, "full_name": "Ops Admin", "password": "strong-password"})
            assert register.status_code == 201, register.text
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
        async with SessionLocal() as db:
            await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": admin_email})
            # One attempt short of the cap, so the next failure is terminal.
            db.add(
                EmailSend(
                    recipient_email=queued_recipient,
                    subject="Receipt",
                    body_html="<p>Hi</p>",
                    status="queued",
                    source="receipt",
                    attempts=MAILING_MAX_ATTEMPTS - 1,
                )
            )
            await db.commit()
        async with SessionLocal() as db:
            stats = await send_pending_emails(db)
        assert stats["failed"] >= 1
        assert any(recipient == admin_email for recipient, _ in alerts)
        assert any("Mail delivery failures" in subject for _, subject in alerts)
    finally:
        async with SessionLocal() as db:
            for address in (queued_recipient, admin_email):
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": address})
            await db.execute(text("DELETE FROM auth_sessions WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": admin_email})
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": admin_email})
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": admin_email})
            await db.commit()
