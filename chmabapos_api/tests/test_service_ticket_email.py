"""Customer email when a serial service ticket is resolved."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend, OrderItem, ProductSerial
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _tickets(recipient: str) -> list[EmailSend]:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(EmailSend).where(EmailSend.recipient_email == recipient, EmailSend.source == "service_ticket")
            )
        ).scalars().all()
        for row in rows:
            db.expunge(row)
        return rows


@pytest.mark.asyncio
async def test_resolved_service_ticket_emails_the_customer() -> None:
    owner_email: str | None = None
    company_id: str | None = None
    customer_email = f"svc-customer-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Service Ticket Store", "Main", plan="starter", email_prefix="service")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={"name": "Service Phone", "sku": f"SV-{uuid.uuid4().hex[:8]}", "price": "200.00", "category_id": category_id, "opening_stock": 5},
                )
            ).json()
            customer = await client.post("/api/v1/customers", headers=headers, json={"name": "Service Buyer", "email": customer_email})
            customer_id = customer.json()["id"]
            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product["id"], "quantity": 1}], "customer_id": customer_id, "payment_method": "cash"},
            )
            assert order.status_code == 201, order.text

        async with SessionLocal() as db:
            item = (await db.execute(select(OrderItem).where(OrderItem.order_id == uuid.UUID(order.json()["id"])))).scalars().first()
            serial = ProductSerial(
                company_id=uuid.UUID(company_id),
                product_id=uuid.UUID(product["id"]),
                store_id=uuid.UUID(ctx["store_id"]),
                serial_number=f"SVSN-{uuid.uuid4().hex[:8]}",
                status="sold",
                order_item_id=item.id,
            )
            db.add(serial)
            await db.commit()
            serial_id = str(serial.id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ticket = await client.post(
                f"/api/v1/serials/{serial_id}/tickets",
                headers=store_headers,
                json={"ticket_type": "repair", "summary": "Screen replacement"},
            )
            assert ticket.status_code == 201, ticket.text
            assert await _tickets(customer_email) == []

            resolved = await client.patch(
                f"/api/v1/tickets/{ticket.json()['id']}",
                headers=store_headers,
                json={"status": "resolved"},
            )
            assert resolved.status_code == 200, resolved.text

        rows = await _tickets(customer_email)
        assert len(rows) == 1
        assert rows[0].subject.startswith("Service complete")
        assert "<!DOCTYPE html>" in rows[0].body_html
    finally:
        async with SessionLocal() as db:
            for address in (email for email in [owner_email, customer_email] if email):
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": address})
            await db.commit()
        if company_id:
            await cleanup_company(company_id, [owner_email] if owner_email else [])
