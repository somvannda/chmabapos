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
            ctx = await register_and_setup(client, "Ticket Store", "Main Floor", plan="pro")
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
async def test_held_orders_with_fractional_quantities_are_returned() -> None:
    # Regression: quantities are stored as decimal strings ("0.500" for weighed
    # goods), so listing them must not coerce to int and 500.
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Weighed Store", "Main", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Rice", "sku": f"FR-{uuid.uuid4().hex[:8]}", "price": "2.00", "unit": "kg", "category_id": category_id, "opening_stock": "10.000"},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]

            held = await client.post(
                "/api/v1/held-orders",
                headers=store_headers,
                json={"label": "Weighed cart", "items": [{"product_id": product_id, "quantity": "0.500"}]},
            )
            assert held.status_code == 201, held.text
            assert held.json()["item_count"] == 0.5
            assert held.json()["items"][0]["quantity"] == 0.5

            listed = await client.get("/api/v1/held-orders", headers=store_headers)
            assert listed.status_code == 200, listed.text
            rows = listed.json()
            assert len(rows) == 1
            assert rows[0]["item_count"] == 0.5
            assert rows[0]["items"][0]["quantity"] == 0.5
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_merging_held_orders_combines_items_and_frees_the_source_table() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Merge Store", "Main", plan="pro")
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
            ctx = await register_and_setup(client, "Split Store", "Main", plan="pro")
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


@pytest.mark.asyncio
async def test_marking_a_ticket_served() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Served Store", "Main", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post("/api/v1/products", headers=store_headers, json={"name": "Soup", "sku": f"SV-{uuid.uuid4().hex[:8]}", "price": "3.00", "category_id": category_id, "opening_stock": 10})
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]
            held = await client.post("/api/v1/held-orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}]})
            assert held.status_code == 201, held.text
            held_id = held.json()["id"]
            assert held.json()["status"] == "open"

            served = await client.patch(f"/api/v1/held-orders/{held_id}", headers=store_headers, json={"status": "served"})
            assert served.status_code == 200 and served.json()["status"] == "served"
            reopened = await client.patch(f"/api/v1/held-orders/{held_id}", headers=store_headers, json={"status": "open"})
            assert reopened.json()["status"] == "open"

            # Unknown status and unknown ticket are rejected.
            assert (await client.patch(f"/api/v1/held-orders/{held_id}", headers=store_headers, json={"status": "napping"})).status_code == 422
            assert (await client.patch("/api/v1/held-orders/00000000-0000-0000-0000-000000000000", headers=store_headers, json={"status": "served"})).status_code == 404
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_held_ticket_carries_variants_and_modifiers() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Held Lines Store", "Main", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Latte", "sku": f"HL-{uuid.uuid4().hex[:8]}", "price": "3.00", "category_id": category_id},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]
            variants = await client.put(
                f"/api/v1/products/{product_id}/variants",
                headers=store_headers,
                json={"variants": [
                    {"sku": f"HL-S-{uuid.uuid4().hex[:6]}", "name": "Small", "opening_stock": 5, "price": "3.00"},
                    {"sku": f"HL-L-{uuid.uuid4().hex[:6]}", "name": "Large", "opening_stock": 5, "price": "4.00"},
                ]},
            )
            assert variants.status_code == 200, variants.text
            by_name = {row["name"]: row["id"] for row in variants.json()["variants"]}

            # The same product with different variants + an add-on are distinct
            # lines on one ticket.
            held = await client.post("/api/v1/held-orders", headers=store_headers, json={"items": [
                {"product_id": product_id, "variant_id": by_name["Large"], "quantity": 1},
                {"product_id": product_id, "variant_id": by_name["Small"], "quantity": 2},
                {"product_id": product_id, "variant_id": by_name["Large"], "quantity": 1, "modifiers": [{"name": "Oat milk", "price_delta": "0.50"}]},
            ]})
            assert held.status_code == 201, held.text
            items = held.json()["items"]
            assert len(items) == 3
            with_addon = next(item for item in items if item["variant_name"] == "Large" and item["modifiers"])
            assert with_addon["unit_price"] == "4.50"
            assert with_addon["modifiers"][0]["name"] == "Oat milk"
            plain = next(item for item in items if item["variant_name"] == "Large" and not item["modifiers"])
            assert plain["unit_price"] == "4.00"
            assert with_addon["line_key"] != plain["line_key"]

            # Split the add-on line onto another table; the source keeps the rest.
            table = (await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "HL1", "seats": 2})).json()["id"]
            held_id = held.json()["id"]
            split = await client.post(f"/api/v1/held-orders/{held_id}/split", headers=store_headers, json={"items": [{"product_id": product_id, "variant_id": by_name["Large"], "quantity": 1, "modifiers": [{"name": "Oat milk", "price_delta": "0.50"}]}], "table_id": table})
            assert split.status_code == 201, split.text
            assert split.json()["items"][0]["unit_price"] == "4.50"
            remaining = {row["id"]: row for row in (await client.get("/api/v1/held-orders", headers=store_headers)).json()}
            assert remaining[held_id]["item_count"] == 3
    finally:
        await cleanup_company(company_id, [email] if email else [])

