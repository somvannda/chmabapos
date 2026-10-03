"""Lifecycle welcome emails: one on confirmation, one when the store is ready.

Both are transactional and best-effort, sent inline through ``app.email``. The
tests capture ``send_email`` so no real delivery is attempted.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_welcome_and_store_ready_emails_are_sent_once(monkeypatch) -> None:
    sent: list[dict] = []

    async def fake_send(recipient, subject, body, **kwargs):
        sent.append({"to": recipient, "subject": subject, "body": body})
        return True

    monkeypatch.setattr("app.email.send_email", fake_send)

    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Welcome Store", "Main", plan="free", email_prefix="welcome")
            email, company_id = ctx["email"], ctx["company_id"]

            welcomes = [message for message in sent if message["subject"] == "Welcome to Chmaba"]
            assert len(welcomes) == 1
            assert welcomes[0]["to"] == email
            assert "/setup/company" in welcomes[0]["body"]

            ready = [message for message in sent if message["subject"] == "Your Chmaba store is ready"]
            assert len(ready) == 1
            assert ready[0]["to"] == email
            assert "Main" in ready[0]["body"]
            assert "/catalog" in ready[0]["body"]
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_welcome_email_is_not_resent_when_verification_repeats(monkeypatch) -> None:
    sent: list[dict] = []

    async def fake_send(recipient, subject, body, **kwargs):
        sent.append({"to": recipient, "subject": subject, "body": body})
        return True

    monkeypatch.setattr("app.email.send_email", fake_send)

    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            email = f"welcome-again-{uuid.uuid4().hex[:8]}@example.com"
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Again Owner", "password": "strong-password"})
            assert register.status_code == 201, register.text
            token = register.json()["dev_verification_token"]
            first = await client.post("/api/v1/auth/verify-email", json={"token": token})
            assert first.status_code == 200, first.text
            # Reusing the token is rejected, so no second welcome can be sent.
            second = await client.post("/api/v1/auth/verify-email", json={"token": token})
            assert second.status_code == 400
            assert len([message for message in sent if message["subject"] == "Welcome to Chmaba"]) == 1
    finally:
        await cleanup_company(company_id, [email] if email else [])
