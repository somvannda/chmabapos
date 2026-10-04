"""New-device sign-in security notice."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.email import send_new_signin_email
from app.main import app
from app.models import AuthSession, User
from app.security import hash_opaque_token
from app.services.sessions import is_new_device
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_new_signin_email_is_branded_html(monkeypatch) -> None:
    captured: dict = {}

    async def fake_send(recipient, subject, body, **kwargs):
        captured.update(recipient=recipient, subject=subject, html=kwargs.get("html"))
        return True

    monkeypatch.setattr("app.email.send_email", fake_send)

    ok = await send_new_signin_email("owner@example.com", "Sokha Chan", device="Chrome on Windows", ip="203.0.113.7")
    assert ok is True
    assert captured["subject"] == "New sign-in to your Chmaba account"
    assert "<!DOCTYPE html>" in captured["html"]
    assert "Sokha" in captured["html"] and "Chrome on Windows" in captured["html"]


@pytest.mark.asyncio
async def test_is_new_device_flags_unseen_agent_only() -> None:
    email = f"new-agent-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register and verify only — do not sign in, so there are no sessions.
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Agent Owner", "password": "strong-password"})
            assert register.status_code == 201, register.text
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})

        async with SessionLocal() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            # A user with no prior sessions is never a "new device".
            assert await is_new_device(db, user.id, user_agent="DeviceA") is False
            db.add(
                AuthSession(
                    user_id=user.id,
                    refresh_token_hash=hash_opaque_token("seed-token"),
                    remember=False,
                    user_agent="DeviceA",
                    ip_address="127.0.0.1",
                    expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                )
            )
            await db.commit()
            assert await is_new_device(db, user.id, user_agent="DeviceA") is False
            assert await is_new_device(db, user.id, user_agent="DeviceB") is True
            assert await is_new_device(db, user.id, user_agent=None) is False
    finally:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
            await db.execute(text("DELETE FROM auth_sessions WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
            await db.commit()


@pytest.mark.asyncio
async def test_login_from_new_device_sends_notice(monkeypatch) -> None:
    sent: list[str] = []

    async def fake_notice(recipient, full_name=None, **kwargs):
        sent.append(kwargs.get("device") or "")
        return True

    monkeypatch.setattr("app.api.v1.send_new_signin_email", fake_notice)

    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "New Device Store", "Main", plan="free", email_prefix="new-login")
            email, company_id = ctx["email"], ctx["company_id"]
            # register_and_setup signed in once (the first session): no notice.
            assert sent == []

            login = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "strong-password"},
                headers={"User-Agent": "FreshDevice/1.0"},
            )
            assert login.status_code == 200, login.text
            assert sent == ["FreshDevice/1.0"]
    finally:
        if email:
            async with SessionLocal() as db:
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
                await db.commit()
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
