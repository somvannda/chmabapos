"""Automatic sale emails: the owner alert and the customer receipt.

Both messages are opt-in per store. The receipt additionally needs the paid
``email_receipts`` capability and a customer email. Delivery rides the
``email_sends`` queue, so these tests inspect the queue and then drain it with
the mail transport stubbed out.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend, EmailSuppression
from app.services.mailing import send_pending_emails
from tests.test_lifecycle import cleanup_company, register_and_setup

SALE_SOURCES = ("sale_alert", "receipt")


async def _queue_rows(emails: list[str]) -> list[EmailSend]:
    cleaned = [email for email in emails if email]
    if not cleaned:
        return []
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(EmailSend)
                .where(EmailSend.recipient_email.in_(cleaned), EmailSend.source.in_(SALE_SOURCES))
                .order_by(EmailSend.created_at)
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
        json={"name": "Sale Latte", "sku": f"SE-{uuid.uuid4().hex[:8]}", "price": "4.50", "category_id": category_id, "opening_stock": 50, "reorder_point": 2},
    )
    assert product.status_code == 201, product.text
    return product.json()["id"]


async def _set_notifications(client: AsyncClient, headers: dict, store_id: str, notifications: dict) -> None:
    updated = await client.patch(f"/api/v1/stores/{store_id}", headers=headers, json={"preferences": {"notifications": notifications}})
    assert updated.status_code == 200, updated.text


async def _cleanup(company_id: str | None, owner_emails: list[str], other_emails: list[str]) -> None:
    emails = [email for email in [*owner_emails, *other_emails] if email]
    if emails:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = ANY(:emails)"), {"emails": emails})
            await db.execute(text("DELETE FROM email_suppressions WHERE lower(email) = ANY(:emails)"), {"emails": [email.lower() for email in emails]})
            await db.commit()
    if company_id:
        await cleanup_company(company_id, owner_emails)


@pytest.mark.asyncio
async def test_sale_emails_are_opt_in_then_queue_and_deliver(monkeypatch) -> None:
    sent: list[tuple[str, str]] = []

    async def fake_send(recipient, subject, body, **kwargs):
        sent.append((recipient, subject))
        return True

    async def fake_marketing(*args, **kwargs):
        return True

    # The queue module imports these names directly, so patch it there.
    monkeypatch.setattr("app.services.mailing.send_email", fake_send)
    monkeypatch.setattr("app.services.mailing.send_marketing_email", fake_marketing)

    owner_email = None
    company_id = None
    customer_email = f"buyer-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Sale Mail Store", "Main", plan="starter", email_prefix="sale")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product_id = await _create_product(client, store_headers)
            customer = await client.post("/api/v1/customers", headers=headers, json={"name": "Buyer One", "email": customer_email})
            assert customer.status_code == 201, customer.text
            customer_id = customer.json()["id"]

            # Off by default: a completed sale queues nothing.
            first = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 2}], "customer_id": customer_id, "payment_method": "cash"},
            )
            assert first.status_code == 201 and first.json()["status"] == "paid", first.text
            assert await _queue_rows([owner_email, customer_email]) == []

            # A customer who unsubscribed from marketing must still get a receipt.
            async with SessionLocal() as db:
                db.add(EmailSuppression(email=customer_email, reason="unsubscribed"))
                await db.commit()

            await _set_notifications(client, headers, ctx["store_id"], {"sale_alert": True, "customer_receipt": True})

            second = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 3}], "customer_id": customer_id, "payment_method": "cash"},
            )
            assert second.status_code == 201, second.text
            order_number = second.json()["order_number"]

            rows = await _queue_rows([owner_email, customer_email])
            by_source = {row.source: row for row in rows}
            assert set(by_source) == {"sale_alert", "receipt"}
            assert by_source["sale_alert"].recipient_email == owner_email
            assert by_source["receipt"].recipient_email == customer_email
            # One email per order, with every line aggregated into it.
            assert order_number in by_source["receipt"].subject
            assert "Buyer One" in by_source["receipt"].body_html
            assert "3 x Sale Latte" in by_source["receipt"].body_html
            assert "Total:" in by_source["sale_alert"].body_html

            async with SessionLocal() as db:
                stats = await send_pending_emails(db)
            assert stats["sent"] >= 2

            drained = {row.source: row for row in await _queue_rows([owner_email, customer_email])}
            # The customer receipt is transactional: unsubscribe must not block it.
            assert drained["receipt"].status == "sent"
            assert drained["sale_alert"].status == "sent"
            assert any(recipient == customer_email and order_number in subject for recipient, subject in sent)
    finally:
        await _cleanup(company_id, [owner_email] if owner_email else [], [customer_email])


@pytest.mark.asyncio
async def test_customer_receipt_stays_off_without_the_paid_capability(monkeypatch) -> None:
    async def fake_send(recipient, subject, body, **kwargs):
        return True

    async def fake_marketing(*args, **kwargs):
        return True

    monkeypatch.setattr("app.services.mailing.send_email", fake_send)
    monkeypatch.setattr("app.services.mailing.send_marketing_email", fake_marketing)

    owner_email = None
    company_id = None
    customer_email = f"free-buyer-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Free Sale Store", "Main", plan="free", email_prefix="sale-free")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product_id = await _create_product(client, store_headers)
            customer = await client.post("/api/v1/customers", headers=headers, json={"name": "Free Buyer", "email": customer_email})
            assert customer.status_code == 201, customer.text
            await _set_notifications(client, headers, ctx["store_id"], {"customer_receipt": True})

            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 1}], "customer_id": customer.json()["id"], "payment_method": "cash"},
            )
            assert order.status_code == 201, order.text
            assert await _queue_rows([customer_email]) == []
    finally:
        await _cleanup(company_id, [owner_email] if owner_email else [], [customer_email])


@pytest.mark.asyncio
async def test_a_failed_delivery_does_not_break_the_sale(monkeypatch) -> None:
    async def failing_send(recipient, subject, body, **kwargs):
        return False

    async def fake_marketing(*args, **kwargs):
        return True

    monkeypatch.setattr("app.services.mailing.send_email", failing_send)
    monkeypatch.setattr("app.services.mailing.send_marketing_email", fake_marketing)

    owner_email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Failure Store", "Main", plan="starter", email_prefix="sale-fail")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product_id = await _create_product(client, store_headers)
            await _set_notifications(client, headers, ctx["store_id"], {"sale_alert": True})

            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"},
            )
            # The sale is unaffected by a mail provider that is down.
            assert order.status_code == 201 and order.json()["status"] == "paid", order.text

            async with SessionLocal() as db:
                await send_pending_emails(db)
            rows = await _queue_rows([owner_email])
            assert len(rows) == 1
            # Attempted, failed, and left queued for the retry backoff.
            assert rows[0].status == "queued"
            assert rows[0].attempts == 1
    finally:
        await _cleanup(company_id, [owner_email] if owner_email else [], [])
