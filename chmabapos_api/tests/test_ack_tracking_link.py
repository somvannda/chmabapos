"""The tracking link in the acknowledgement email.

A regression here would be silent: the caller wraps the acknowledgement in a
try/except that logs and carries on, so a broken template or a missing import
stops the email reaching the customer with nothing failing loudly. These tests
therefore assert the message is still produced, not just that the link appears.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _acks(recipient: str) -> list[EmailSend]:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(EmailSend).where(
                    EmailSend.recipient_email == recipient, EmailSend.source == "online_order_ack"
                )
            )
        ).scalars().all()
        for row in rows:
            db.expunge(row)
        return rows


@pytest.mark.asyncio
async def test_acknowledgement_carries_a_tracking_link_only_when_configured(monkeypatch) -> None:
    owner_email: str | None = None
    company_id: str | None = None
    customer_email = f"tracking-buyer-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Ack Link {suffix}", f"Till {suffix}", email_prefix="ack-link")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            category_id = (await client.get("/api/v1/categories", headers=ctx["headers"])).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={
                        "name": "Tracked Item",
                        "sku": f"AL-{suffix}",
                        "price": "4.00",
                        "category_id": category_id,
                        "opening_stock": 5,
                    },
                )
            ).json()
            enabled = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            token = enabled.json()["token"]

            # With no storefront host configured, the email must still be produced -
            # just without a link, rather than with a broken one.
            monkeypatch.setattr(settings, "storefront_url", "")
            submitted = await client.post(
                f"/api/v1/public/order/{token}",
                json={
                    "items": [{"product_id": product["id"], "quantity": 1}],
                    "customer_name": "Sokha",
                    "customer_email": customer_email,
                },
            )
            assert submitted.status_code == 201, submitted.text
            unlinked = await _acks(customer_email)
            assert len(unlinked) == 1, "the acknowledgement must still be sent"
            assert "Follow your order" not in unlinked[0].body_html
            assert "/order/" not in unlinked[0].body_html

            # With a host configured, the link is present and absolute.
            monkeypatch.setattr(settings, "storefront_url", "https://shops.example.com/")
            async with SessionLocal() as db:
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": customer_email})
                await db.commit()
            again = await client.post(
                f"/api/v1/public/order/{token}",
                json={
                    "items": [{"product_id": product["id"], "quantity": 1}],
                    "customer_name": "Sokha",
                    "customer_email": customer_email,
                },
            )
            assert again.status_code == 201, again.text
            linked = await _acks(customer_email)
            assert len(linked) == 1, "the acknowledgement must still be sent with a host configured"
            html = linked[0].body_html
            assert "Follow your order" in html
            # The trailing slash on the setting must not double up.
            assert "https://shops.example.com/order/" in html
            assert "example.com//order/" not in html
    finally:
        monkeypatch.setattr(settings, "storefront_url", "")
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": customer_email})
            await db.commit()
        if company_id:
            await cleanup_company(company_id, [owner_email] if owner_email else [])
