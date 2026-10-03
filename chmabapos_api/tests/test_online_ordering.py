from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


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
