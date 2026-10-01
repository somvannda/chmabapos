from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_opening_a_ticket_occupies_the_table_and_settling_frees_it() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Ticket Store", "Main Floor", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Fried Rice", "sku": f"TK-{uuid.uuid4().hex[:8]}", "price": "3.50", "category_id": category_id, "opening_stock": 20},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]

            table = await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "T1", "seats": 4})
            assert table.status_code == 201, table.text
            table_id = table.json()["id"]

            # Open a dine-in ticket against the table.
            held = await client.post(
                "/api/v1/held-orders",
                headers=store_headers,
                json={"label": "Table T1", "order_type": "dine_in", "table_id": table_id, "items": [{"product_id": product_id, "quantity": 2}]},
            )
            assert held.status_code == 201, held.text
            assert held.json()["table_id"] == table_id
            assert held.json()["status"] == "open"

            # The table is now occupied.
            tables = (await client.get("/api/v1/dining/tables", headers=store_headers)).json()
            assert tables[0]["status"] == "occupied"

            # Settling/discarding the last ticket frees the table.
            assert (await client.delete(f"/api/v1/held-orders/{held.json()['id']}", headers=store_headers)).status_code == 200
            tables = (await client.get("/api/v1/dining/tables", headers=store_headers)).json()
            assert tables[0]["status"] == "available"

            # An unknown table is rejected.
            missing = await client.post(
                "/api/v1/held-orders",
                headers=store_headers,
                json={"table_id": "00000000-0000-0000-0000-000000000000", "items": [{"product_id": product_id, "quantity": 1}]},
            )
            assert missing.status_code == 400
    finally:
        await cleanup_company(company_id, [email] if email else [])
