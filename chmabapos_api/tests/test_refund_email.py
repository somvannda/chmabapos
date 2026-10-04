"""The buyer's refund confirmation email."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _rows(source: str, recipient: str) -> list[EmailSend]:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(EmailSend).where(EmailSend.source == source, EmailSend.recipient_email == recipient)
            )
        ).scalars().all()
        for row in rows:
            db.expunge(row)
        return rows


@pytest.mark.asyncio
async def test_refund_confirmation_emails_the_customer() -> None:
    owner_email: str | None = None
    company_id: str | None = None
    customer_email = f"refund-buyer-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Refund Mail Store", "Main", plan="starter", email_prefix="refund-mail")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product_id = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={"name": "Refund Latte", "sku": f"RF-{uuid.uuid4().hex[:8]}", "price": "4.50", "category_id": category_id, "opening_stock": 50},
                )
            ).json()["id"]
            customer_id = (
                await client.post("/api/v1/customers", headers=headers, json={"name": "Refund Buyer", "email": customer_email})
            ).json()["id"]
            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 2}], "customer_id": customer_id, "payment_method": "cash"},
            )
            assert order.status_code == 201, order.text
            refund = await client.post(
                f"/api/v1/orders/{order.json()['id']}/refund",
                headers=store_headers,
                json={"method": "cash", "items": [{"product_id": product_id, "quantity": 2}]},
            )
            assert refund.status_code == 201, refund.text

            rows = await _rows("refund_confirmation", customer_email)
            assert len(rows) == 1
            assert rows[0].subject.startswith("Refund processed")
            assert "<!DOCTYPE html>" in rows[0].body_html
            assert order.json()["order_number"] in rows[0].body_html
    finally:
        async with SessionLocal() as db:
            for address in (email for email in [owner_email, customer_email] if email):
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": address})
            await db.commit()
        if company_id:
            await cleanup_company(company_id, [owner_email] if owner_email else [])
