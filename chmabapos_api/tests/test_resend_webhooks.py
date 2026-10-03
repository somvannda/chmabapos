"""Resend webhook verification and bounce/complaint suppression."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend, EmailSuppression
from app.services import mail as mail_service
from app.services import mailing as mailing_service
from app.services.mail_events import verify_svix_signature

WEBHOOK_SECRET = "whsec_" + base64.b64encode(b"chmaba-test-webhook-key").decode()


def svix_headers(secret: str, payload: bytes, *, timestamp: int | None = None, message_id: str = "msg_test") -> dict:
    ts = timestamp if timestamp is not None else int(datetime.now(timezone.utc).timestamp())
    raw = secret[len("whsec_") :] if secret.startswith("whsec_") else secret
    key = base64.b64decode(raw)
    signed = f"{message_id}.{ts}.".encode() + payload
    signature = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    return {"svix-id": message_id, "svix-timestamp": str(ts), "svix-signature": f"v1,{signature}"}


async def cleanup(address: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": address})
        await db.execute(text("DELETE FROM email_suppressions WHERE email = :email"), {"email": address})
        await db.execute(text("DELETE FROM platform_settings WHERE key = 'resend_webhook_secret'"))
        await db.commit()


def test_svix_signature_verification() -> None:
    payload = b'{"type":"email.bounced"}'
    headers = svix_headers(WEBHOOK_SECRET, payload)
    assert verify_svix_signature(
        secret=WEBHOOK_SECRET,
        payload=payload,
        svix_id=headers["svix-id"],
        svix_timestamp=headers["svix-timestamp"],
        svix_signature=headers["svix-signature"],
    )
    # A tampered body, a wrong secret, a stale timestamp and missing headers all fail.
    assert not verify_svix_signature(secret=WEBHOOK_SECRET, payload=b'{"type":"x"}', svix_id=headers["svix-id"], svix_timestamp=headers["svix-timestamp"], svix_signature=headers["svix-signature"])
    other = svix_headers("whsec_" + base64.b64encode(b"another-key").decode(), payload)
    assert not verify_svix_signature(secret=WEBHOOK_SECRET, payload=payload, svix_id=other["svix-id"], svix_timestamp=other["svix-timestamp"], svix_signature=other["svix-signature"])
    old = svix_headers(WEBHOOK_SECRET, payload, timestamp=int(datetime.now(timezone.utc).timestamp()) - 3600)
    assert not verify_svix_signature(secret=WEBHOOK_SECRET, payload=payload, svix_id=old["svix-id"], svix_timestamp=old["svix-timestamp"], svix_signature=old["svix-signature"])
    assert not verify_svix_signature(secret=WEBHOOK_SECRET, payload=payload, svix_id=None, svix_timestamp=None, svix_signature=None)


@pytest.mark.asyncio
async def test_bounce_suppresses_and_flags_then_blocks_future_sends() -> None:
    address = f"bounce-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with SessionLocal() as db:
            await mail_service.save_mail_settings(db, {"resend_webhook_secret": WEBHOOK_SECRET})
            db.add(EmailSend(recipient_email=address, subject="Hi", body_html="<p>Hi</p>", status="sent", source="manual"))
            await db.commit()

        payload = json.dumps({"type": "email.bounced", "data": {"to": [address], "bounce": {"type": "hard", "message": "mailbox does not exist"}}}).encode()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/webhooks/resend", content=payload, headers=svix_headers(WEBHOOK_SECRET, payload))
        assert response.status_code == 200
        body = response.json()
        assert body["event"] == "email.bounced"
        assert body["suppressed"] == 1
        assert body["flagged"] == 1

        async with SessionLocal() as db:
            suppression = (await db.execute(select(EmailSuppression).where(EmailSuppression.email == address))).scalars().one()
            assert suppression.reason == "bounced"
            row = (await db.execute(select(EmailSend).where(EmailSend.recipient_email == address))).scalars().one()
            assert row.status == "bounced"
            assert "mailbox does not exist" in row.error

        # The address is now on the suppression list, so future sends skip it.
        async with SessionLocal() as db:
            assert await mailing_service.suppressed_emails(db, [address]) == {address}

        # A replayed/tampered payload is rejected.
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            bad = await client.post("/api/v1/webhooks/resend", content=payload, headers={"svix-id": "x", "svix-timestamp": "1", "svix-signature": "v1,deadbeef"})
        assert bad.status_code == 401
    finally:
        await cleanup(address)


@pytest.mark.asyncio
async def test_complaint_and_unconfigured_webhook() -> None:
    address = f"complaint-{uuid.uuid4().hex[:8]}@example.com"
    try:
        payload = json.dumps({"type": "email.complained", "data": {"to": address}}).encode()

        # No secret configured: the endpoint refuses rather than trusting input.
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM platform_settings WHERE key = 'resend_webhook_secret'"))
            await db.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            unconfigured = await client.post("/api/v1/webhooks/resend", content=payload, headers=svix_headers(WEBHOOK_SECRET, payload))
        assert unconfigured.status_code == 503

        async with SessionLocal() as db:
            await mail_service.save_mail_settings(db, {"resend_webhook_secret": WEBHOOK_SECRET})
            db.add(EmailSend(recipient_email=address, subject="Hi", body_html="<p>Hi</p>", status="queued", source="drip"))
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/webhooks/resend", content=payload, headers=svix_headers(WEBHOOK_SECRET, payload))
        assert response.status_code == 200
        assert response.json()["suppressed"] == 1

        async with SessionLocal() as db:
            suppression = (await db.execute(select(EmailSuppression).where(EmailSuppression.email == address))).scalars().one()
            assert suppression.reason == "complained"
            row = (await db.execute(select(EmailSend).where(EmailSend.recipient_email == address))).scalars().one()
            assert row.status == "complained"
            # Dropped from the queue so it will not be retried.
            assert row.next_attempt_at is None
    finally:
        await cleanup(address)


@pytest.mark.asyncio
async def test_delivery_events_advance_the_log() -> None:
    address = f"tracked-{uuid.uuid4().hex[:8]}@example.com"
    message_id = f"re_{uuid.uuid4().hex[:10]}"
    try:
        async with SessionLocal() as db:
            await mail_service.save_mail_settings(db, {"resend_webhook_secret": WEBHOOK_SECRET})
            db.add(
                EmailSend(
                    recipient_email=address,
                    subject="Hi",
                    body_html="<p>Hi</p>",
                    status="sent",
                    source="manual",
                    provider="resend",
                    provider_message_id=message_id,
                )
            )
            await db.commit()

        async def post(event_type: str, data: dict) -> dict:
            payload = json.dumps({"type": event_type, "data": data}).encode()
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/webhooks/resend", content=payload, headers=svix_headers(WEBHOOK_SECRET, payload))
            assert response.status_code == 200
            return response.json()

        # Events can arrive out of order; the row keeps the furthest stage.
        assert (await post("email.opened", {"email_id": message_id, "to": [address]}))["tracked"] == 1
        assert (await post("email.delivered", {"email_id": message_id, "to": [address]}))["tracked"] == 1
        assert (await post("email.clicked", {"email_id": message_id, "to": [address]}))["tracked"] == 1

        async with SessionLocal() as db:
            row = (await db.execute(select(EmailSend).where(EmailSend.provider_message_id == message_id))).scalars().one()
            assert row.delivered_at is not None
            assert row.opened_at is not None
            assert row.clicked_at is not None
            assert row.status == "clicked"
            assert (await db.execute(select(EmailSuppression).where(EmailSuppression.email == address))).scalars().all() == []
    finally:
        await cleanup(address)


@pytest.mark.asyncio
async def test_unrelated_event_types_are_ignored() -> None:
    address = f"ignored-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with SessionLocal() as db:
            await mail_service.save_mail_settings(db, {"resend_webhook_secret": WEBHOOK_SECRET})
            db.add(EmailSend(recipient_email=address, subject="Hi", body_html="<p>Hi</p>", status="sent", source="manual"))
            await db.commit()

        payload = json.dumps({"type": "email.received", "data": {"to": [address]}}).encode()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/webhooks/resend", content=payload, headers=svix_headers(WEBHOOK_SECRET, payload))
        assert response.status_code == 200
        body = response.json()
        assert body["suppressed"] == 0
        assert body["tracked"] == 0

        async with SessionLocal() as db:
            row = (await db.execute(select(EmailSend).where(EmailSend.recipient_email == address))).scalars().one()
            assert row.status == "sent"
            assert row.delivered_at is None
    finally:
        await cleanup(address)
