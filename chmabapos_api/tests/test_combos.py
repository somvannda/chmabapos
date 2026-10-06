from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _create_product(client, store_headers, category_id: str, name: str, price: str, stock: int = 20) -> dict:
    response = await client.post(
        "/api/v1/products",
        headers=store_headers,
        json={"name": name, "sku": f"CB-{uuid.uuid4().hex[:8]}", "price": price, "category_id": category_id, "opening_stock": stock},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _on_hand(client, store_headers, product_id: str) -> float:
    products = (await client.get("/api/v1/products", headers=store_headers)).json()
    return next(product["on_hand"] for product in products if product["id"] == product_id)


@pytest.mark.asyncio
async def test_combo_sale_depletes_components_and_refund_restores_them() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Combo Store", "Main Counter", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]

            burger = await _create_product(client, store_headers, category_id, "Burger", "5.00")
            fries = await _create_product(client, store_headers, category_id, "Fries", "2.00")
            drink = await _create_product(client, store_headers, category_id, "Drink", "1.50")

            created = await client.post(
                "/api/v1/combos",
                headers=store_headers,
                json={
                    "name": "Meal Deal",
                    "sku": f"MEAL-{uuid.uuid4().hex[:6]}",
                    "price": "6.50",
                    "items": [
                        {"product_id": burger["id"], "quantity": 1},
                        {"product_id": fries["id"], "quantity": 1},
                        {"product_id": drink["id"], "quantity": 2},
                    ],
                },
            )
            assert created.status_code == 201, created.text
            combo = created.json()
            assert [item["product_name"] for item in combo["items"]] == ["Burger", "Fries", "Drink"]
            assert combo["items"][2]["quantity"] == 2

            listed = await client.get("/api/v1/combos", headers=store_headers)
            assert listed.status_code == 200
            assert [row["id"] for row in listed.json()] == [combo["id"]]

            sale = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"combo_id": combo["id"], "quantity": 1}], "payment_method": "cash"})
            assert sale.status_code == 201, sale.text
            order = sale.json()
            line = order["items"][0]
            assert line["combo_id"] == combo["id"]
            assert line["combo_name"] == "Meal Deal"
            assert line["product_id"] == burger["id"]  # lead component
            assert order["subtotal"] == "6.50"
            assert [component["name"] for component in line["combo_components"]] == ["Burger", "Fries", "Drink"]

            # A combo is logical: each component's stock is drawn down.
            assert await _on_hand(client, store_headers, burger["id"]) == 19
            assert await _on_hand(client, store_headers, fries["id"]) == 19
            assert await _on_hand(client, store_headers, drink["id"]) == 18

            refund = await client.post(
                f"/api/v1/orders/{order['id']}/refund",
                headers=store_headers,
                json={"items": [{"product_id": burger["id"], "quantity": 1}]},
            )
            assert refund.status_code == 201, refund.text
            assert await _on_hand(client, store_headers, burger["id"]) == 20
            assert await _on_hand(client, store_headers, fries["id"]) == 20
            assert await _on_hand(client, store_headers, drink["id"]) == 20
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_combo_validation_rejects_bad_input() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Combo Validation", "Main")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await _create_product(client, store_headers, category_id, "Wrap", "4.00")

            # A combo must reference real products of the company.
            bad = await client.post("/api/v1/combos", headers=store_headers, json={"name": "Bad", "price": "1.00", "items": [{"product_id": "00000000-0000-0000-0000-000000000000", "quantity": 1}]})
            assert bad.status_code == 400

            # An order line is either a product or a combo, never both.
            both = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product["id"], "combo_id": "00000000-0000-0000-0000-000000000000", "quantity": 1}], "payment_method": "cash"})
            assert both.status_code == 422

            # An unknown combo is refused.
            unknown = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"combo_id": "00000000-0000-0000-0000-000000000000", "quantity": 1}], "payment_method": "cash"})
            assert unknown.status_code == 400
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_combo_refund_targets_the_right_line_by_order_item_id() -> None:
    """Two combos sharing a lead component must refund the line that was chosen."""
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Combo Split Store", "Main Counter", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            burger = await _create_product(client, store_headers, category_id, "Burger", "5.00")
            fries = await _create_product(client, store_headers, category_id, "Fries", "2.00")
            drink = await _create_product(client, store_headers, category_id, "Drink", "1.50")

            combo_a = await client.post("/api/v1/combos", headers=store_headers, json={"name": "Meal A", "sku": f"A-{uuid.uuid4().hex[:6]}", "price": "6.50", "items": [{"product_id": burger["id"], "quantity": 1}, {"product_id": fries["id"], "quantity": 1}]})
            combo_b = await client.post("/api/v1/combos", headers=store_headers, json={"name": "Meal B", "sku": f"B-{uuid.uuid4().hex[:6]}", "price": "5.00", "items": [{"product_id": burger["id"], "quantity": 1}, {"product_id": drink["id"], "quantity": 2}]})
            assert combo_a.status_code == 201 and combo_b.status_code == 201, combo_a.text + combo_b.text
            combo_a, combo_b = combo_a.json(), combo_b.json()

            sale = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"combo_id": combo_a["id"], "quantity": 1}, {"combo_id": combo_b["id"], "quantity": 1}], "payment_method": "cash"})
            assert sale.status_code == 201, sale.text
            order = sale.json()
            # Both lines share the lead component (Burger), so only the order-item id tells them apart.
            assert {line["product_id"] for line in order["items"]} == {burger["id"]}
            line_b = next(line for line in order["items"] if line["combo_id"] == combo_b["id"])

            assert await _on_hand(client, store_headers, burger["id"]) == 18
            assert await _on_hand(client, store_headers, fries["id"]) == 19
            assert await _on_hand(client, store_headers, drink["id"]) == 18

            refund = await client.post(
                f"/api/v1/orders/{order['id']}/refund",
                headers=store_headers,
                json={"method": "cash", "items": [{"product_id": burger["id"], "order_item_id": line_b["id"], "quantity": 1}]},
            )
            assert refund.status_code == 201, refund.text
            # Only Meal B's components come back on the shelf.
            assert await _on_hand(client, store_headers, burger["id"]) == 19
            assert await _on_hand(client, store_headers, fries["id"]) == 19
            assert await _on_hand(client, store_headers, drink["id"]) == 20
    finally:
        await cleanup_company(company_id, [email] if email else [])
