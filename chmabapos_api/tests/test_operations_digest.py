"""Daily operations digest of in-app-only events."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend, Notification, User
from app.services.store_notifications import run_store_notifications
from tests.test_lifecycle import cleanup_company, register_and_setup

EVENING_UTC = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)  # 21:00 local


async def _notes(owner_email: str | None) -> list[EmailSend]:
    if not owner_email:
        return []
    async with SessionLocal() as db:
        rows = (
            await db.execute(select(EmailSend).where(EmailSend.recipient_email == owner_email, EmailSend.source == "store_note"))
        ).scalars().all()
        for row in rows:
            db.expunge(row)
        return rows


@pytest.mark.asyncio
async def test_operations_digest_emails_owner_once_a_day() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Ops Digest Store", "Main", plan="free", email_prefix="ops-digest")
            email, company_id = ctx["email"], ctx["company_id"]
            headers = ctx["headers"]

            # Off by default: no digest even with an event present.
            async with SessionLocal() as db:
                user = (await db.execute(select(User).where(User.email == email))).scalar_one()
                db.add(
                    Notification(
                        store_id=uuid.UUID(ctx["store_id"]),
                        user_id=user.id,
                        type="stock_transfer",
                        title="Incoming stock transfer",
                        body="3 item(s) in transit",
                        created_at=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
                    )
                )
                await db.commit()
                await run_store_notifications(db, now=EVENING_UTC)
            assert await _notes(email) == []

            await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"preferences": {"notifications": {"operations_digest": True}}})
            async with SessionLocal() as db:
                stats = await run_store_notifications(db, now=EVENING_UTC)
            assert stats["operations_digests"] == 1
            notes = await _notes(email)
            assert len(notes) == 1
            assert notes[0].subject.startswith("Operations summary")
            assert "Incoming stock transfer" in notes[0].body_html

            # A second run the same day must not double-send.
            async with SessionLocal() as db:
                again = await run_store_notifications(db, now=EVENING_UTC)
            assert again["operations_digests"] == 0
            assert len(await _notes(email)) == 1
    finally:
        if email:
            async with SessionLocal() as db:
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
                await db.execute(text("DELETE FROM notifications WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)"), {"company_id": company_id})
                await db.commit()
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
