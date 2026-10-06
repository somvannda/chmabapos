"""Report revenue must reflect the order-level discount, not the pre-discount lines."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_reports_attribute_the_order_discount() -> None:
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Margin Discount Store", "Main", plan="starter", email_prefix="margin-disc")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product = (await client.post("/api/v1/products", headers=store_headers, json={"name": "Margin Item", "sku": f"MG-{uuid.uuid4().hex[:8]}", "price": "100.00", "opening_stock": 5})).json()
            order = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product["id"], "quantity": 2}], "discount": "40.00", "payment_method": "cash"})
            assert order.status_code == 201, order.text

            margin = await client.get("/api/v1/reports/margin", headers=store_headers)
            assert margin.status_code == 200, margin.text
            body = margin.json()
            # 200 subtotal - 40 discount = 160 attributable revenue (pre-tax).
            assert Decimal(str(body["revenue"])) == Decimal("160.00")
            row = next(item for item in body["rows"] if item["product_id"] == product["id"])
            assert Decimal(str(row["revenue"])) == Decimal("160.00")

            condition = await client.get("/api/v1/reports/condition", headers=store_headers)
            assert condition.status_code == 200, condition.text
            assert Decimal(str(condition.json()["revenue"])) == Decimal("160.00")
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
