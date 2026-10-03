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
        json={"name": name, "sku": f"CR-{uuid.uuid4().hex[:8]}", "price": price, "category_id": category_id, "opening_stock": stock},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_combo_sales_are_reported_separately_from_products() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Combo Reports", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]

            fries = await _create_product(client, store_headers, category_id, "Fries", "2.00")
            burger = await _create_product(client, store_headers, category_id, "Burger", "5.00")
            standalone = await _create_product(client, store_headers, category_id, "Soda", "1.50")

            created = await client.post(
                "/api/v1/combos",
                headers=store_headers,
                json={
                    "name": "Meal",
                    "price": "6.50",
                    "items": [{"product_id": fries["id"], "quantity": 1}],
                    "groups": [{"name": "Main", "min_select": 1, "max_select": 1, "options": [{"product_id": burger["id"]}]}],
                },
            )
            assert created.status_code == 201, created.text
            combo = created.json()
            main_group = combo["groups"][0]
            burger_option = main_group["options"][0]

            sale = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"combo_id": combo["id"], "quantity": 1, "combo_selections": [{"group_id": main_group["id"], "option_id": burger_option["id"]}]}], "payment_method": "cash"},
            )
            assert sale.status_code == 201, sale.text
            standalone_sale = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": standalone["id"], "quantity": 2}], "payment_method": "cash"})
            assert standalone_sale.status_code == 201, standalone_sale.text

            summary = await client.get("/api/v1/reports/summary", headers=store_headers)
            assert summary.status_code == 200, summary.text
            body = summary.json()
            combos = {row["name"]: row for row in body["top_combos"]}
            assert "Meal" in combos
            assert combos["Meal"]["amount"] == "6.50"
            # The combo is not double-counted under its lead component.
            assert all(row["name"] != "Meal" for row in body["top_products"])
            product_names = {row["name"] for row in body["top_products"]}
            assert "Soda" in product_names
            assert "Fries" not in product_names and "Burger" not in product_names

            margin = await client.get("/api/v1/reports/margin", headers=store_headers)
            assert margin.status_code == 200, margin.text
            margin_body = margin.json()
            combo_rows = {row["combo_name"]: row for row in margin_body["combos"]}
            assert combo_rows["Meal"]["revenue"] == "6.50"
            # Standalone product still appears in the per-product rows.
            assert any(row["product_name"] == "Soda" for row in margin_body["rows"])
            assert all(row["product_name"] != "Meal" for row in margin_body["rows"])
    finally:
        await cleanup_company(company_id, [email] if email else [])
