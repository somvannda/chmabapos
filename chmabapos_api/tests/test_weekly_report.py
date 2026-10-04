"""Weekly sales summary email."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
from app.services.store_notifications import run_store_notifications
from tests.test_lifecycle import cleanup_company, register_and_setup

# Monday 14:00 UTC is Monday 21:00 in Asia/Phnom_Penh, past the summary hour.
MONDAY_EVENING_UTC = datetime(2026, 1, 5, 14, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_weekly_report_is_opt_in_and_sends_once_a_week() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Weekly Store", "Main", plan="free", email_prefix="weekly")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={"name": "Weekly Latte", "sku": f"WK-{uuid.uuid4().hex[:8]}", "price": "5.00", "category_id": category_id, "opening_stock": 20},
                )
            ).json()
            await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product["id"], "quantity": 2}], "payment_method": "cash"})

            # Off by default: nothing is queued.
            async with SessionLocal() as db:
                await run_store_notifications(db, now=MONDAY_EVENING_UTC)
            assert await _notes(email) == []

            await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"preferences": {"notifications": {"weekly_report": True}}})
            async with SessionLocal() as db:
                stats = await run_store_notifications(db, now=MONDAY_EVENING_UTC)
            assert stats["weekly_reports"] == 1
            notes = await _notes(email)
            assert len(notes) == 1
            assert notes[0].subject.startswith("Weekly summary")
            assert "<!DOCTYPE html>" in notes[0].body_html

            # A second run the same week must not double-send.
            async with SessionLocal() as db:
                again = await run_store_notifications(db, now=MONDAY_EVENING_UTC)
            assert again["weekly_reports"] == 0
            assert len(await _notes(email)) == 1
    finally:
        if email:
            async with SessionLocal() as db:
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
                await db.commit()
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


async def _notes(owner_email: str | None) -> list[EmailSend]:
    if not owner_email:
        return []
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(EmailSend).where(EmailSend.recipient_email == owner_email, EmailSend.source == "store_note")
            )
        ).scalars().all()
        for row in rows:
            db.expunge(row)
        return rows
