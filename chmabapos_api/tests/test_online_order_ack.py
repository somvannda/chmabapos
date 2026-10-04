"""Customer acknowledgement email for a public online/QR order."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _acks(recipient: str) -> list[EmailSend]:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(EmailSend).where(EmailSend.recipient_email == recipient, EmailSend.source == "online_order_ack")
            )
        ).scalars().all()
        for row in rows:
            db.expunge(row)
        return rows


@pytest.mark.asyncio
async def test_public_order_acknowledges_the_customer() -> None:
    owner_email: str | None = None
    company_id: str | None = None
    customer_email = f"online-buyer-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Online Ack Store", "Main", plan="pro", email_prefix="online-ack")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={"name": "Ack Latte", "sku": f"AK-{uuid.uuid4().hex[:8]}", "price": "4.50", "category_id": category_id, "opening_stock": 10},
                )
            ).json()
            settings = await client.patch(f"/api/v1/stores/{ctx['store_id']}/public-order", headers=headers, json={"enabled": True})
            assert settings.status_code == 200, settings.text
            token = settings.json()["token"]

            # No email in the payload: no acknowledgement.
            anonymous = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product["id"], "quantity": 1}]})
            assert anonymous.status_code == 201, anonymous.text
            assert await _acks(customer_email) == []

            submitted = await client.post(
                f"/api/v1/public/order/{token}",
                json={"items": [{"product_id": product["id"], "quantity": 2}], "customer_name": "Sokha", "customer_email": customer_email},
            )
            assert submitted.status_code == 201, submitted.text

            acks = await _acks(customer_email)
            assert len(acks) == 1
            assert acks[0].subject.startswith("Order received")
            assert "<!DOCTYPE html>" in acks[0].body_html
            assert "Ack Latte" in acks[0].body_html
    finally:
        async with SessionLocal() as db:
            for address in (email for email in [owner_email, customer_email] if email):
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": address})
            await db.commit()
        if company_id:
            await cleanup_company(company_id, [owner_email] if owner_email else [])
