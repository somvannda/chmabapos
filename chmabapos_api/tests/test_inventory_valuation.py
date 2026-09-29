"""Inventory valuation and report-projection fields.

``/inventory`` now exposes the retail price and the cost basis (product and
variant level) so the storefront can present potential revenue and margin, and
``/reports/summary`` exposes a trailing run rate. These are presentation-only
additions, but they must be populated from the catalog and stay internally
consistent.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_inventory_exposes_price_and_cost_for_valuation() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Valuation Store", "Valuation Counter", plan="starter", email_prefix="value")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]

            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={
                    "name": "Valuation Widget",
                    "sku": f"VW-{uuid.uuid4().hex[:8]}",
                    "price": "10.00",
                    "cost_price": "4.00",
                    "category_id": category_id,
                    "opening_stock": 5,
                    "reorder_point": 1,
                },
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]

            rows = (await client.get("/api/v1/inventory", headers=store_headers)).json()
            row = next(item for item in rows if item["product_id"] == product_id)
            assert row["price"] == "10.00"
            assert row["cost_price"] == "4.00"
            assert row["on_hand"] == 5

            # Variants carry their own price/cost so a mixed catalog values correctly.
            variants = await client.put(
                f"/api/v1/products/{product_id}/variants",
                headers=store_headers,
                json={"variants": [{"sku": f"VW-128-{uuid.uuid4().hex[:6]}", "name": "128GB", "price": "12.00", "cost_price": "5.00", "opening_stock": 3}]},
            )
            assert variants.status_code == 200, variants.text

            rows_after = (await client.get("/api/v1/inventory", headers=store_headers)).json()
            row_after = next(item for item in rows_after if item["product_id"] == product_id)
            variant_row = row_after["variants"][0]
            assert variant_row["price"] == "12.00"
            assert variant_row["cost_price"] == "5.00"

            # A product without a recorded cost must report null, never zero.
            no_cost = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "No Cost Widget", "sku": f"NC-{uuid.uuid4().hex[:8]}", "price": "7.00", "category_id": category_id, "opening_stock": 2},
            )
            assert no_cost.status_code == 201, no_cost.text
            rows_final = (await client.get("/api/v1/inventory", headers=store_headers)).json()
            no_cost_row = next(item for item in rows_final if item["product_id"] == no_cost.json()["id"])
            assert no_cost_row["cost_price"] is None
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_report_summary_exposes_run_rate_projection() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Projection Store", "Projection Counter", plan="starter", email_prefix="proj")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]

            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Projection Widget", "sku": f"PW-{uuid.uuid4().hex[:8]}", "price": "10.00", "cost_price": "4.00", "category_id": category_id, "opening_stock": 20, "reorder_point": 1},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]

            sale = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 3}], "payment_method": "cash"})
            assert sale.status_code == 201 and sale.json()["status"] == "paid", sale.text

            report = await client.get("/api/v1/reports/summary", headers=store_headers)
            assert report.status_code == 200, report.text
            body = report.json()

            # Default window is month-to-date, so the sale today is in range.
            assert body["days_in_period"] >= 1
            expected_daily = round(float(body["net_after_refunds"]) / body["days_in_period"], 2)
            assert abs(float(body["average_daily_net"]) - expected_daily) <= 0.01
            assert abs(float(body["projected_next_30_days"]) - float(body["average_daily_net"]) * 30) <= 0.01
    finally:
        await cleanup_company(company_id, [email] if email else [])
