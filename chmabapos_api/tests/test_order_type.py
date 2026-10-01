from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_order_type_round_trips_and_defaults_to_takeaway() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Order Type Store", "Main Counter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Spring Rolls", "sku": f"OT-{uuid.uuid4().hex[:8]}", "price": "5.00", "category_id": category_id, "opening_stock": 20},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]

            # Default is takeaway, so existing "pay and go" orders are unchanged.
            default = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"})
            assert default.status_code == 201, default.text
            assert default.json()["order_type"] == "takeaway"

            # Dine-in round-trips through create and read.
            dine = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash", "order_type": "dine_in"})
            assert dine.status_code == 201, dine.text
            assert dine.json()["order_type"] == "dine_in"
            fetched = await client.get(f"/api/v1/orders/{dine.json()['id']}", headers=store_headers)
            assert fetched.json()["order_type"] == "dine_in"

            # Held orders carry the intended fulfilment too.
            held = await client.post("/api/v1/held-orders", headers=store_headers, json={"label": "Table 4", "order_type": "dine_in", "items": [{"product_id": product_id, "quantity": 1}]})
            assert held.status_code == 201, held.text
            assert held.json()["order_type"] == "dine_in"

            # An unknown value is rejected at the boundary.
            bad = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash", "order_type": "brunch"})
            assert bad.status_code == 422
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_order_can_snapshot_a_dining_table() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Order Table Store", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Table Dish", "sku": f"OT-{uuid.uuid4().hex[:8]}", "price": "6.00", "category_id": category_id, "opening_stock": 20},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]
            table = await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "T9", "seats": 2})
            assert table.status_code == 201, table.text
            table_id = table.json()["id"]

            sale = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash", "order_type": "dine_in", "table_id": table_id})
            assert sale.status_code == 201, sale.text
            assert sale.json()["table_id"] == table_id
            fetched = await client.get(f"/api/v1/orders/{sale.json()['id']}", headers=store_headers)
            assert fetched.json()["table_id"] == table_id

            # An unknown table is rejected.
            bad = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash", "table_id": "00000000-0000-0000-0000-000000000000"})
            assert bad.status_code == 400
    finally:
        await cleanup_company(company_id, [email] if email else [])
