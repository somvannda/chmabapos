from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _alerts(owner_email: str | None) -> list[EmailSend]:
    if not owner_email:
        return []
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(EmailSend)
                .where(EmailSend.recipient_email == owner_email, EmailSend.source == "store_note")
                .order_by(EmailSend.created_at)
            )
        ).scalars().all()
        for row in rows:
            db.expunge(row)
        return rows


@pytest.mark.asyncio
async def test_public_ordering_menu_and_submit() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Online Store", "Main", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (await client.post("/api/v1/products", headers=store_headers, json={"name": "Latte", "sku": f"ON-{uuid.uuid4().hex[:8]}", "price": "3.50", "category_id": category_id, "opening_stock": 10})).json()
            table = (await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "T1", "seats": 2})).json()

            # Off until enabled.
            assert (await client.get("/api/v1/public/order/badtoken")).status_code == 404

            settings = await client.patch(f"/api/v1/stores/{ctx['store_id']}/public-order", headers=headers, json={"enabled": True})
            assert settings.status_code == 200, settings.text
            token = settings.json()["token"]
            assert token

            menu = await client.get(f"/api/v1/public/order/{token}")
            assert menu.status_code == 200, menu.text
            assert menu.json()["store_name"] == "Main"
            assert menu.json()["table_name"] is None
            assert any(item["id"] == product["id"] and item["available"] for item in menu.json()["items"])

            # A table QR token resolves to the table and marks the ticket as qr.
            table_menu = await client.get(f"/api/v1/public/order/{table['qr_token']}")
            assert table_menu.status_code == 200
            assert table_menu.json()["table_name"] == "T1"

            submitted = await client.post(
                f"/api/v1/public/order/{token}",
                json={"items": [{"product_id": product["id"], "quantity": 2}], "customer_note": "No sugar"},
            )
            assert submitted.status_code == 201, submitted.text
            ticket = submitted.json()
            assert ticket["source"] == "online"
            assert ticket["table_id"] is None
            assert ticket["created_by"] is None
            assert ticket["customer_note"] == "No sugar"
            assert ticket["subtotal"] == "7.00"

            at_table = await client.post(f"/api/v1/public/order/{table['qr_token']}", json={"items": [{"product_id": product["id"], "quantity": 1}]})
            assert at_table.status_code == 201, at_table.text
            assert at_table.json()["source"] == "qr"
            assert at_table.json()["table_id"] == table["id"]

            # Disabling closes the public surface again.
            await client.patch(f"/api/v1/stores/{ctx['store_id']}/public-order", headers=headers, json={"enabled": False})
            assert (await client.get(f"/api/v1/public/order/{token}")).status_code == 404
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_online_order_alerts_owner_when_enabled() -> None:
    """A public order emails owners once the ``online_order`` toggle is on, and
    stays silent while it is off."""
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Online Alert Store", "Main", plan="pro", email_prefix="online-alert")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={"name": "Alert Latte", "sku": f"OA-{uuid.uuid4().hex[:8]}", "price": "3.50", "category_id": category_id, "opening_stock": 10},
                )
            ).json()
            settings = await client.patch(f"/api/v1/stores/{ctx['store_id']}/public-order", headers=headers, json={"enabled": True})
            assert settings.status_code == 200, settings.text
            token = settings.json()["token"]

            # Off by default: submitting queues no owner alert.
            submitted = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product["id"], "quantity": 1}]})
            assert submitted.status_code == 201, submitted.text
            assert await _alerts(email) == []

            await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"preferences": {"notifications": {"online_order": True}}})
            submitted = await client.post(
                f"/api/v1/public/order/{token}",
                json={"items": [{"product_id": product["id"], "quantity": 2}], "customer_note": "No sugar"},
            )
            assert submitted.status_code == 201, submitted.text

            alerts = await _alerts(email)
            assert len(alerts) == 1
            assert alerts[0].subject.startswith("New online order")
            assert "<!DOCTYPE html>" in alerts[0].body_html
            assert "Alert Latte" in alerts[0].body_html
            assert "No sugar" in alerts[0].body_html
    finally:
        if email:
            async with SessionLocal() as db:
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
                await db.commit()
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_public_menu_exposes_and_sells_variants() -> None:
    """A product with sizes shows one option per variant and sells the chosen one."""
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Variant Store", "Main", plan="pro", email_prefix="online-variant")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product = (await client.post("/api/v1/products", headers=store_headers, json={"name": "Latte", "sku": f"VAR-{uuid.uuid4().hex[:8]}", "price": "3.50"})).json()
            variants = (
                await client.put(
                    f"/api/v1/products/{product['id']}/variants",
                    headers=store_headers,
                    json={"variants": [
                        {"sku": f"SM-{uuid.uuid4().hex[:6]}", "name": "Small", "price": "3.50", "opening_stock": 3},
                        {"sku": f"LG-{uuid.uuid4().hex[:6]}", "name": "Large", "price": "4.50", "opening_stock": 2},
                    ]},
                )
            ).json()["variants"]
            small = next(variant for variant in variants if variant["name"] == "Small")
            large = next(variant for variant in variants if variant["name"] == "Large")

            token = (await client.patch(f"/api/v1/stores/{ctx['store_id']}/public-order", headers=headers, json={"enabled": True})).json()["token"]

            menu = await client.get(f"/api/v1/public/order/{token}")
            assert menu.status_code == 200, menu.text
            item = next(row for row in menu.json()["items"] if row["id"] == product["id"])
            assert item["available"] is True
            by_name = {variant["name"]: variant for variant in item["variants"]}
            assert set(by_name) == {"Small", "Large"}
            assert by_name["Large"]["price"] == "4.50"
            assert by_name["Large"]["available"] is True

            submitted = await client.post(
                f"/api/v1/public/order/{token}",
                json={"items": [{"product_id": product["id"], "variant_id": large["id"], "quantity": 2}]},
            )
            assert submitted.status_code == 201, submitted.text
            line = submitted.json()["items"][0]
            assert line["variant_id"] == large["id"]
            assert line["variant_name"] == "Large"
            assert line["unit_price"] == "4.50"
            assert submitted.json()["subtotal"] == "9.00"

            # Selling beyond a variant's stock is rejected.
            too_many = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product["id"], "variant_id": small["id"], "quantity": 99}]})
            assert too_many.status_code == 409
    finally:
        await cleanup_company(company_id, [email] if email else [])
