"""Cost snapshot tests: COGS is frozen onto the sale line.

The key invariant is that editing a product's catalog ``cost_price`` after a
sale must not rewrite that sale's reported margin. Receipt costs feed a
weighted average that is captured per order line at fulfillment.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def margin_for_today(client: AsyncClient, store_headers: dict) -> dict:
    response = await client.get("/api/v1/reports/margin", headers=store_headers)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_sale_cost_is_frozen_against_later_catalog_edits() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Cost Store", "Cost Counter", plan="starter", email_prefix="cost")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]

            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Cost Widget", "sku": f"CW-{uuid.uuid4().hex[:8]}", "price": "10.00", "category_id": category_id, "reorder_point": 1},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]

            # Two receipts at different costs -> weighted average (10*4 + 10*6) / 20 = 5.00
            first = await client.post(f"/api/v1/inventory/{product_id}/restock", headers=store_headers, json={"quantity": 10, "unit_cost": "4.00", "supplier": "Vendor A"})
            assert first.status_code == 200, first.text
            second = await client.post(f"/api/v1/inventory/{product_id}/restock", headers=store_headers, json={"quantity": 10, "unit_cost": "6.00", "supplier": "Vendor B"})
            assert second.status_code == 200, second.text
            assert second.json()["on_hand"] == 20

            # Sell 4 units at 10.00: cost frozen at 5.00 each -> cost 20.00, margin 20.00.
            sale = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 4}], "payment_method": "cash"})
            assert sale.status_code == 201 and sale.json()["status"] == "paid", sale.text

            report = await margin_for_today(client, store_headers)
            row = next(entry for entry in report["rows"] if entry["product_id"] == product_id)
            assert row["quantity"] == 4
            assert row["revenue"] == "40.00"
            assert row["cost"] == "20.00"
            assert row["margin"] == "20.00"

            # Editing catalog cost must not rewrite the historical margin.
            patched = await client.patch(f"/api/v1/products/{product_id}", headers=store_headers, json={"cost_price": "99.00"})
            assert patched.status_code == 200, patched.text

            report_after = await margin_for_today(client, store_headers)
            row_after = next(entry for entry in report_after["rows"] if entry["product_id"] == product_id)
            assert row_after["cost"] == "20.00"
            assert row_after["margin"] == "20.00"

            # A later sale still uses the receipt weighted average, not the edited cost.
            later = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"})
            assert later.status_code == 201 and later.json()["status"] == "paid", later.text

            report_final = await margin_for_today(client, store_headers)
            row_final = next(entry for entry in report_final["rows"] if entry["product_id"] == product_id)
            assert row_final["quantity"] == 5
            assert row_final["cost"] == "25.00"
            assert row_final["margin"] == "25.00"
    finally:
        await cleanup_company(company_id, [email] if email else [])
