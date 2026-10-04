"""Ops alert when a queued email exhausts its retries."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
from app.services.mailing import _alert_dead_letters


@pytest.mark.asyncio
async def test_dead_letter_alert_notifies_platform_admins(monkeypatch) -> None:
    admin_email = f"ops-admin-{uuid.uuid4().hex[:8]}@example.com"
    sent: list[str] = []

    async def fake_send(recipient, subject, text, html=None, **kwargs):
        sent.append(recipient)
        return True, None

    monkeypatch.setattr("app.services.mailing.send_email_with_id", fake_send)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": admin_email, "full_name": "Ops Admin", "password": "strong-password"})
            assert register.status_code == 201, register.text
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
        async with SessionLocal() as db:
            await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": admin_email})
            row = EmailSend(
                recipient_email="buyer@example.com",
                subject="Receipt",
                body_html="<p>Hi</p>",
                status="failed",
                source="receipt",
                error="Delivery failed after 5 attempts",
                attempts=5,
            )
            db.add(row)
            await db.flush()
            # Call the alert directly: it must not drain (or disturb) the queue.
            await _alert_dead_letters(db, [row])
            await db.commit()

        assert admin_email in sent
    finally:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": admin_email})
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": "buyer@example.com"})
            await db.execute(text("DELETE FROM auth_sessions WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": admin_email})
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": admin_email})
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": admin_email})
            await db.commit()
