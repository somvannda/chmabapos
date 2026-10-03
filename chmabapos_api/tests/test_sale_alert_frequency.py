"""Owner sale-alert frequency: every sale vs a once-a-day digest.

The per-order alert is queued by ``queue_sale_emails`` (source ``sale_alert``);
the digest is queued by the scheduler ``run_store_notifications`` (source
``store_note``). Both respect the ``sale_alert`` toggle.
"""
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

EVENING_UTC = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)
SALE_SOURCES = ("sale_alert", "store_note")


async def _notes(emails: list[str]) -> list[EmailSend]:
    cleaned = [email for email in emails if email]
    if not cleaned:
        return []
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(EmailSend).where(EmailSend.recipient_email.in_(cleaned), EmailSend.source.in_(SALE_SOURCES)).order_by(EmailSend.created_at)
            )
        ).scalars().all()
        for row in rows:
            db.expunge(row)
        return rows


async def _create_product(client: AsyncClient, store_headers: dict) -> str:
    category_id = (await client.get("/api/v1/categories", headers=store_headers)).json()[0]["id"]
    product = await client.post(
        "/api/v1/products",
        headers=store_headers,
        json={"name": "Freq Latte", "sku": f"FQ-{uuid.uuid4().hex[:8]}", "price": "4.50", "category_id": category_id, "opening_stock": 50, "reorder_point": 2},
    )
    assert product.status_code == 201, product.text
    return product.json()["id"]


async def _set_notifications(client: AsyncClient, headers: dict, store_id: str, notifications: dict) -> None:
    updated = await client.patch(f"/api/v1/stores/{store_id}", headers=headers, json={"preferences": {"notifications": notifications}})
    assert updated.status_code == 200, updated.text


async def _cleanup(company_id: str | None, owner_email: str | None) -> None:
    if owner_email:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": owner_email})
            await db.commit()
    if company_id:
        await cleanup_company(company_id, [owner_email] if owner_email else [])


@pytest.mark.asyncio
async def test_daily_frequency_sends_one_digest_and_no_per_sale_alert(monkeypatch) -> None:
    owner_email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Freq Store", "Main", plan="free", email_prefix="freq-daily")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product_id = await _create_product(client, store_headers)
            await _set_notifications(client, headers, ctx["store_id"], {"sale_alert": True, "sale_alert_frequency": "daily"})

            order = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 2}], "payment_method": "cash"})
            assert order.status_code == 201, order.text
            # Daily mode: nothing is sent at the moment of sale.
            assert await _notes([owner_email]) == []

            # 14:00 UTC on the order's own date is 21:00 local, so the digest day
            # covers the sale regardless of when the test runs.
            created = order.json()["created_at"].replace("Z", "+00:00")
            day = datetime.fromisoformat(created).date()
            evening = datetime(day.year, day.month, day.day, 14, 0, tzinfo=timezone.utc)

            async with SessionLocal() as db:
                stats = await run_store_notifications(db, now=evening)
            assert stats["sale_digests"] == 1
            notes = await _notes([owner_email])
            assert len(notes) == 1
            assert "Sales today" in notes[0].subject
            assert order.json()["order_number"] in notes[0].body_html

            # A second run the same local day must not double-send.
            async with SessionLocal() as db:
                again = await run_store_notifications(db, now=evening)
            assert again["sale_digests"] == 0
            assert len(await _notes([owner_email])) == 1
    finally:
        await _cleanup(company_id, owner_email)


@pytest.mark.asyncio
async def test_every_sale_frequency_sends_per_order_and_no_digest(monkeypatch) -> None:
    owner_email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Freq Every Store", "Main", plan="free", email_prefix="freq-every")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product_id = await _create_product(client, store_headers)
            # No frequency set -> every_sale (the default).
            await _set_notifications(client, headers, ctx["store_id"], {"sale_alert": True})

            order = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"})
            assert order.status_code == 201, order.text
            notes = await _notes([owner_email])
            assert len(notes) == 1 and notes[0].source == "sale_alert"
            assert "New sale" in notes[0].subject

            async with SessionLocal() as db:
                stats = await run_store_notifications(db, now=EVENING_UTC)
            assert stats["sale_digests"] == 0
    finally:
        await _cleanup(company_id, owner_email)
