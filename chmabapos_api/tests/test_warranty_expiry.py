"""Weekly reminder for customer warranties about to expire."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend, ProductSerial
from app.services.store_notifications import run_store_notifications
from tests.test_lifecycle import cleanup_company, register_and_setup

# Monday 14:00 UTC is Monday 21:00 local (UTC+7), past the summary hour.
MONDAY_EVENING_UTC = datetime(2026, 1, 5, 14, 0, tzinfo=timezone.utc)


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
async def test_warranty_expiry_reminds_owner() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Warranty Store", "Main", plan="free", email_prefix="warranty")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={"name": "Warranty Phone", "sku": f"WR-{uuid.uuid4().hex[:8]}", "price": "100.00", "category_id": category_id},
                )
            ).json()

        async with SessionLocal() as db:
            db.add(
                ProductSerial(
                    company_id=uuid.UUID(company_id),
                    product_id=uuid.UUID(product["id"]),
                    store_id=uuid.UUID(ctx["store_id"]),
                    serial_number=f"SN-{uuid.uuid4().hex[:8]}",
                    status="sold",
                    sold_at=datetime(2025, 12, 1, tzinfo=timezone.utc),
                    customer_warranty_until=MONDAY_EVENING_UTC + timedelta(days=15),
                )
            )
            await db.commit()

        # Off by default.
        async with SessionLocal() as db:
            await run_store_notifications(db, now=MONDAY_EVENING_UTC)
        assert await _notes(email) == []

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"preferences": {"notifications": {"warranty_expiry": True}}})
        async with SessionLocal() as db:
            stats = await run_store_notifications(db, now=MONDAY_EVENING_UTC)
        assert stats["warranty_expiries"] == 1
        notes = await _notes(email)
        assert len(notes) == 1
        assert notes[0].subject.startswith("Warranties expiring")
        assert "Warranty Phone" in notes[0].body_html
    finally:
        if email:
            async with SessionLocal() as db:
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
                await db.commit()
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
