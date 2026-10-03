"""Store notification emails: the Settings → Notifications toggles.

Time-based notes (daily summary, low stock, shift reminders) are produced by the
scheduler ``run_store_notifications``; event notes (refund, team activity) are
queued by the action itself. All of them go through the ``email_sends`` outbox
with the ``store_note`` source, so these tests inspect the outbox.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend, Shift
from app.services.store_notifications import run_store_notifications
from tests.test_lifecycle import cleanup_company, register_and_setup

# 14:00 UTC is 21:00 in Asia/Phnom_Penh, past the daily-summary hour.
EVENING_UTC = datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc)


async def _notes(emails: list[str]) -> list[EmailSend]:
    cleaned = [email for email in emails if email]
    if not cleaned:
        return []
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(EmailSend).where(EmailSend.recipient_email.in_(cleaned), EmailSend.source == "store_note").order_by(EmailSend.created_at)
            )
        ).scalars().all()
        for row in rows:
            db.expunge(row)
        return rows


async def _set_notifications(client: AsyncClient, headers: dict, store_id: str, notifications: dict) -> None:
    updated = await client.patch(f"/api/v1/stores/{store_id}", headers=headers, json={"preferences": {"notifications": notifications}})
    assert updated.status_code == 200, updated.text


async def _create_product(client: AsyncClient, store_headers: dict, *, stock: int = 2, reorder: int = 10) -> str:
    category_id = (await client.get("/api/v1/categories", headers=store_headers)).json()[0]["id"]
    product = await client.post(
        "/api/v1/products",
        headers=store_headers,
        json={"name": "Notify Latte", "sku": f"NT-{uuid.uuid4().hex[:8]}", "price": "4.50", "category_id": category_id, "opening_stock": stock, "reorder_point": reorder},
    )
    assert product.status_code == 201, product.text
    return product.json()["id"]


async def _cleanup(company_id: str | None, owner_email: str | None) -> None:
    if owner_email:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": owner_email})
            await db.commit()
    if company_id:
        await cleanup_company(company_id, [owner_email] if owner_email else [])


@pytest.mark.asyncio
async def test_daily_summary_and_low_stock_are_opt_in_and_deduped(monkeypatch) -> None:
    owner_email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Notify Store", "Main", plan="free", email_prefix="notify")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product_id = await _create_product(client, store_headers, stock=2, reorder=10)
            order = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"})
            assert order.status_code == 201, order.text

            # Off by default: the scheduler queues nothing.
            async with SessionLocal() as db:
                await run_store_notifications(db, now=EVENING_UTC)
            assert await _notes([owner_email]) == []

            await _set_notifications(client, headers, ctx["store_id"], {"daily_summary": True, "low_stock_alerts": True})

            async with SessionLocal() as db:
                stats = await run_store_notifications(db, now=EVENING_UTC)
            assert stats["summaries"] == 1 and stats["low_stock"] == 1
            notes = await _notes([owner_email])
            subjects = sorted(note.subject for note in notes)
            assert any("Daily summary" in subject for subject in subjects)
            assert any("Low stock alert" in subject for subject in subjects)
            summary = next(note for note in notes if "Daily summary" in note.subject)
            assert "Orders:" in summary.body_html and "Main" in summary.subject

            # A second run the same local day must not double-send.
            async with SessionLocal() as db:
                again = await run_store_notifications(db, now=EVENING_UTC)
            assert again["summaries"] == 0 and again["low_stock"] == 0
            assert len(await _notes([owner_email])) == 2
    finally:
        await _cleanup(company_id, owner_email)


@pytest.mark.asyncio
async def test_refund_activity_emails_the_owner(monkeypatch) -> None:
    owner_email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Refund Notify Store", "Main", plan="starter", email_prefix="notify-refund")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product_id = await _create_product(client, store_headers, stock=20, reorder=2)
            await _set_notifications(client, headers, ctx["store_id"], {"refund_activity": True})

            order = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"})
            assert order.status_code == 201, order.text
            assert await _notes([owner_email]) == []

            refund = await client.post(
                f"/api/v1/orders/{order.json()['id']}/refund",
                headers=store_headers,
                json={"method": "cash", "items": [{"product_id": product_id, "quantity": 1}]},
            )
            assert refund.status_code == 201, refund.text
            notes = await _notes([owner_email])
            assert len(notes) == 1 and "Refund" in notes[0].subject
    finally:
        await _cleanup(company_id, owner_email)


@pytest.mark.asyncio
async def test_team_activity_emails_the_owner(monkeypatch) -> None:
    owner_email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Team Notify Store", "Main", plan="starter", email_prefix="notify-team")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            headers = ctx["headers"]
            await _set_notifications(client, headers, ctx["store_id"], {"team_activity": True})

            invitation = await client.post("/api/v1/team/invitations", headers=headers, json={"email": f"member-{uuid.uuid4().hex[:8]}@example.com", "role": "manager"})
            assert invitation.status_code == 201, invitation.text
            notes = await _notes([owner_email])
            assert len(notes) == 1 and "Team invite" in notes[0].subject
    finally:
        await _cleanup(company_id, owner_email)


@pytest.mark.asyncio
async def test_shift_reminder_fires_once_per_open_shift(monkeypatch) -> None:
    owner_email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Shift Notify Store", "Main", plan="starter", email_prefix="notify-shift")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            await _set_notifications(client, headers, ctx["store_id"], {"shift_reminders": True})

            opened = await client.post("/api/v1/shifts/open", headers=store_headers, json={"opening_float": 0})
            assert opened.status_code == 201, opened.text

            now = datetime.now(timezone.utc)
            # Make the shift look like it has been open for 13 hours.
            async with SessionLocal() as db:
                shift = (await db.execute(select(Shift).where(Shift.id == uuid.UUID(opened.json()["id"])))).scalar_one()
                shift.opened_at = now - timedelta(hours=13)
                await db.commit()
                stats = await run_store_notifications(db, now=now)
            assert stats["shift_reminders"] == 1
            notes = await _notes([owner_email])
            assert len(notes) == 1 and "Shift still open" in notes[0].subject

            # Already reminded for this shift.
            async with SessionLocal() as db:
                again = await run_store_notifications(db, now=now)
            assert again["shift_reminders"] == 0
            assert len(await _notes([owner_email])) == 1
    finally:
        await _cleanup(company_id, owner_email)
