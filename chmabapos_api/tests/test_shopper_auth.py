"""Shopper sign-in with an emailed code.

Covers the two things most likely to be got wrong: that the endpoints cannot be
used to discover who shops here, and that a shopper identity is genuinely separate
from a staff one.
"""
from __future__ import annotations

import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
from app.security import decode_token


async def _latest_code(email: str) -> str | None:
    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(EmailSend)
                .where(EmailSend.recipient_email == email, EmailSend.source == "shopper_signin")
                .order_by(EmailSend.created_at.desc())
            )
        ).scalars().first()
    if row is None:
        return None
    match = re.search(r"<strong>(\d{6})</strong>", row.body_html or "")
    return match.group(1) if match else None


async def _purge(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM shopper_email_codes WHERE shopper_id IN (SELECT id FROM shopper_accounts WHERE email = :e)"), {"e": email})
        await db.execute(text("DELETE FROM shopper_accounts WHERE email = :e"), {"e": email})
        await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :e"), {"e": email})
        await db.commit()


@pytest.mark.asyncio
async def test_shopper_signs_in_with_an_emailed_code() -> None:
    email = f"shopper-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            requested = await client.post("/api/v1/public/auth/email-code", json={"email": email})
            assert requested.status_code == 202, requested.text
            assert requested.json() == {"status": "code_sent"}

            code = await _latest_code(email)
            assert code, "a sign-in code should have been queued"

            verified = await client.post("/api/v1/public/auth/verify", json={"email": email, "code": code})
            assert verified.status_code == 200, verified.text
            body = verified.json()
            assert body["shopper"]["email"] == email
            assert body["shopper"]["is_email_verified"] is True

            # The token is a shopper token, not a staff access token. This is what
            # keeps the two identity systems from being interchangeable.
            payload = decode_token(body["access_token"])
            assert payload["type"] == "shopper"

            # ... and a staff endpoint must refuse it. The reverse (a staff token
            # on a shopper endpoint) is enforced by the same type check.
            staff = await client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
            )
            assert staff.status_code == 401, f"a shopper token must not authenticate staff: {staff.text}"

            # Codes are single use.
            reused = await client.post("/api/v1/public/auth/verify", json={"email": email, "code": code})
            assert reused.status_code == 400, reused.text

            # The token identifies the shopper, but only to shopper endpoints.
            me = await client.get("/api/v1/public/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
            assert me.status_code == 200, me.text
            assert me.json()["email"] == email
            assert me.json()["id"] == body["shopper"]["id"]
            # ... and says nothing beyond what the shopper may see about themselves.
            assert "google_sub" not in me.json() and "telegram_id" not in me.json()
    finally:
        await _purge(email)


@pytest.mark.asyncio
async def test_code_request_does_not_reveal_whether_an_account_exists() -> None:
    known = f"shopper-known-{uuid.uuid4().hex[:10]}@example.com"
    unknown = f"shopper-unknown-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post("/api/v1/public/auth/email-code", json={"email": known})
            assert first.status_code == 202

            # The same call for an address nobody has used must look identical.
            second = await client.post("/api/v1/public/auth/email-code", json={"email": unknown})
            assert second.status_code == first.status_code
            assert second.json() == first.json()

            # A wrong code is refused, and says the same thing an unknown account
            # would: one message for every failure, so it cannot be used to probe.
            wrong = await client.post("/api/v1/public/auth/verify", json={"email": known, "code": "000000"})
            assert wrong.status_code == 400
            missing = await client.post("/api/v1/public/auth/verify", json={"email": unknown, "code": "000000"})
            assert missing.status_code == 400
            assert missing.json()["detail"] == wrong.json()["detail"]
    finally:
        await _purge(known)
        await _purge(unknown)
