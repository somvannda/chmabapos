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


@pytest.mark.asyncio
async def test_merging_held_orders_combines_items_and_frees_the_source_table() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Merge Store", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Noodles", "sku": f"MG-{uuid.uuid4().hex[:8]}", "price": "2.00", "category_id": category_id, "opening_stock": 30},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]

            t1 = (await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "M1", "seats": 2})).json()["id"]
            t2 = (await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "M2", "seats": 2})).json()["id"]

            a = await client.post("/api/v1/held-orders", headers=store_headers, json={"order_type": "dine_in", "table_id": t1, "items": [{"product_id": product_id, "quantity": 1}]})
            b = await client.post("/api/v1/held-orders", headers=store_headers, json={"order_type": "dine_in", "table_id": t2, "items": [{"product_id": product_id, "quantity": 2}]})
            assert a.status_code == 201 and b.status_code == 201, (a.text, b.text)

            merged = await client.post(f"/api/v1/held-orders/{a.json()['id']}/merge", headers=store_headers, json={"into_id": b.json()["id"]})
            assert merged.status_code == 200, merged.text
            assert merged.json()["item_count"] == 3
            assert merged.json()["table_id"] == t2

            # The source ticket is gone and its table is free again.
            remaining = (await client.get("/api/v1/held-orders", headers=store_headers)).json()
            assert len(remaining) == 1 and remaining[0]["id"] == b.json()["id"]
            tables = {row["id"]: row["status"] for row in (await client.get("/api/v1/dining/tables", headers=store_headers)).json()}
            assert tables[t1] == "available" and tables[t2] == "occupied"

            # Merging into itself, or into an unknown ticket, is rejected.
            assert (await client.post(f"/api/v1/held-orders/{b.json()['id']}/merge", headers=store_headers, json={"into_id": b.json()["id"]})).status_code == 400
            assert (await client.post(f"/api/v1/held-orders/{b.json()['id']}/merge", headers=store_headers, json={"into_id": "00000000-0000-0000-0000-000000000000"})).status_code == 404
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_splitting_a_held_order_moves_lines_to_a_new_ticket() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Split Store", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Dumplings", "sku": f"SP-{uuid.uuid4().hex[:8]}", "price": "2.00", "category_id": category_id, "opening_stock": 30},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]
            t1 = (await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "S1", "seats": 2})).json()["id"]
            t2 = (await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "S2", "seats": 2})).json()["id"]

            original = await client.post("/api/v1/held-orders", headers=store_headers, json={"order_type": "dine_in", "table_id": t1, "items": [{"product_id": product_id, "quantity": 5}]})
            assert original.status_code == 201, original.text
            original_id = original.json()["id"]

            split = await client.post(f"/api/v1/held-orders/{original_id}/split", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 2}], "table_id": t2})
            assert split.status_code == 201, split.text
            assert split.json()["item_count"] == 2 and split.json()["table_id"] == t2

            tickets = {row["id"]: row for row in (await client.get("/api/v1/held-orders", headers=store_headers)).json()}
            assert len(tickets) == 2
            assert tickets[original_id]["item_count"] == 3
            tables = {row["id"]: row["status"] for row in (await client.get("/api/v1/dining/tables", headers=store_headers)).json()}
            assert tables[t1] == "occupied" and tables[t2] == "occupied"

            # Cannot split more than is on the ticket, nor an item that is not on it.
            assert (await client.post(f"/api/v1/held-orders/{original_id}/split", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 99}]})).status_code == 400
            assert (await client.post(f"/api/v1/held-orders/{original_id}/split", headers=store_headers, json={"items": [{"product_id": "00000000-0000-0000-0000-000000000000", "quantity": 1}]})).status_code == 400
    finally:
        await cleanup_company(company_id, [email] if email else [])
