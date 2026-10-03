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
        json={"name": name, "sku": f"CC-{uuid.uuid4().hex[:8]}", "price": price, "category_id": category_id, "opening_stock": stock},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _on_hand(client, store_headers, product_id: str) -> float:
    products = (await client.get("/api/v1/products", headers=store_headers)).json()
    return next(product["on_hand"] for product in products if product["id"] == product_id)


async def _setup_choice_combo(client, headers, store_headers):
    category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
    fries = await _create_product(client, store_headers, category_id, "Fries", "2.00")
    burger = await _create_product(client, store_headers, category_id, "Burger", "5.00")
    chicken = await _create_product(client, store_headers, category_id, "Chicken", "5.50")
    cola = await _create_product(client, store_headers, category_id, "Cola", "1.00")
    water = await _create_product(client, store_headers, category_id, "Water", "0.50")
    created = await client.post(
        "/api/v1/combos",
        headers=store_headers,
        json={
            "name": "Combo A",
            "sku": f"COMBO-{uuid.uuid4().hex[:6]}",
            "price": "6.50",
            "items": [{"product_id": fries["id"], "quantity": 1}],
            "groups": [
                {
                    "name": "Main",
                    "min_select": 1,
                    "max_select": 1,
                    "options": [
                        {"product_id": burger["id"], "price_delta": "0.00"},
                        {"product_id": chicken["id"], "price_delta": "1.00"},
                    ],
                },
                {
                    "name": "Drink",
                    "min_select": 1,
                    "max_select": 2,
                    "options": [
                        {"product_id": cola["id"], "price_delta": "0.00"},
                        {"product_id": water["id"], "price_delta": "0.00"},
                    ],
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    combo = created.json()
    group_ids = {group["name"]: group["id"] for group in combo["groups"]}
    option_ids = {option["product_id"]: option["id"] for group in combo["groups"] for option in group["options"]}
    return combo, {
        "fries": fries,
        "burger": burger,
        "chicken": chicken,
        "cola": cola,
        "water": water,
        "main_group": group_ids["Main"],
        "drink_group": group_ids["Drink"],
        "option_chicken": option_ids[chicken["id"]],
        "option_cola": option_ids[cola["id"]],
    }


@pytest.mark.asyncio
async def test_choice_combo_declares_groups_sells_and_restores_choices() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Choice Combo Store", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            combo, p = await _setup_choice_combo(client, headers, store_headers)

            assert [group["name"] for group in combo["groups"]] == ["Main", "Drink"]
            assert combo["groups"][1]["max_select"] == 2

            sale = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [
                        {
                            "combo_id": combo["id"],
                            "quantity": 1,
                            "combo_selections": [
                                {"group_id": p["main_group"], "option_id": p["option_chicken"]},
                                {"group_id": p["drink_group"], "option_id": p["option_cola"]},
                            ],
                        }
                    ],
                    "payment_method": "cash",
                },
            )
            assert sale.status_code == 201, sale.text
            order = sale.json()
            line = order["items"][0]
            assert line["combo_name"] == "Combo A"
            # 6.50 base + 1.00 chicken delta.
            assert line["unit_price"] == "7.50"
            names = [component["name"] for component in line["combo_components"]]
            assert names == ["Fries", "Chicken", "Cola"]
            by_name = {component["name"]: component for component in line["combo_components"]}
            assert by_name["Chicken"]["group_name"] == "Main"
            assert by_name["Cola"]["group_name"] == "Drink"
            assert "group_name" not in by_name["Fries"]

            # Only the fixed item and the chosen options are depleted.
            assert await _on_hand(client, store_headers, p["fries"]["id"]) == 19
            assert await _on_hand(client, store_headers, p["chicken"]["id"]) == 19
            assert await _on_hand(client, store_headers, p["cola"]["id"]) == 19
            assert await _on_hand(client, store_headers, p["burger"]["id"]) == 20
            assert await _on_hand(client, store_headers, p["water"]["id"]) == 20

            refund = await client.post(
                f"/api/v1/orders/{order['id']}/refund",
                headers=store_headers,
                json={"items": [{"product_id": p["fries"]["id"], "quantity": 1}]},
            )
            assert refund.status_code == 201, refund.text
            assert await _on_hand(client, store_headers, p["fries"]["id"]) == 20
            assert await _on_hand(client, store_headers, p["chicken"]["id"]) == 20
            assert await _on_hand(client, store_headers, p["cola"]["id"]) == 20
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_choice_combo_validation() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Choice Combo Validation", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            combo, p = await _setup_choice_combo(client, headers, store_headers)
            base_item = {"combo_id": combo["id"], "quantity": 1}

            # Required groups must be satisfied.
            missing = await client.post("/api/v1/orders", headers=store_headers, json={"items": [base_item], "payment_method": "cash"})
            assert missing.status_code == 400

            # An option from another group is rejected.
            wrong_group = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{**base_item, "combo_selections": [
                        {"group_id": p["main_group"], "option_id": p["option_cola"]},
                        {"group_id": p["drink_group"], "option_id": p["option_cola"]},
                    ]}],
                    "payment_method": "cash",
                },
            )
            assert wrong_group.status_code == 400

            # Exceeding max_select is rejected.
            too_many = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{**base_item, "combo_selections": [
                        {"group_id": p["main_group"], "option_id": p["option_chicken"], "quantity": 2},
                        {"group_id": p["drink_group"], "option_id": p["option_cola"]},
                    ]}],
                    "payment_method": "cash",
                },
            )
            assert too_many.status_code == 400

            # A group option must reference a real product.
            bad = await client.post(
                "/api/v1/combos",
                headers=store_headers,
                json={"name": "Bad", "price": "1.00", "groups": [{"name": "Pick", "min_select": 1, "max_select": 1, "options": [{"product_id": "00000000-0000-0000-0000-000000000000"}]}]},
            )
            assert bad.status_code == 400
    finally:
        await cleanup_company(company_id, [email] if email else [])
