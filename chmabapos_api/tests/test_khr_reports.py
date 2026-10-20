"""A KHR sales report is in whole riel.

Every figure a manager reads off the summary - gross, net, tax, average order, the
product breakdown - is money in the store's currency, so on a KHR store it is whole
riel. The handler quantised all of them to two decimals regardless.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_a_khr_summary_report_is_whole_riel() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Riel Report Co", "Main", plan="pro", email_prefix="khr-report")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]

            enabled = await client.put(
                "/api/v1/settings/currencies", headers=headers, json={"primary_code": "USD", "enabled_codes": ["USD", "KHR"]}
            )
            assert enabled.status_code == 200, enabled.text
            configured = await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"currency_code": "KHR"})
            assert configured.status_code == 200, configured.text

            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={"name": "Report Item", "sku": f"RPT-{uuid.uuid4().hex[:8]}", "price": "3333", "category_id": category_id, "opening_stock": 5},
                )
            ).json()
            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product["id"], "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "KHR", "amount": "3666"}],
                },
            )
            assert order.status_code == 201, order.text

            report = await client.get("/api/v1/reports/summary", headers=store_headers)
            assert report.status_code == 200, report.text
            body = report.json()

            assert body["gross_sales"] == "3333", body
            assert body["tax"] == "333", body
            assert body["net_sales"] == "3666", body
            assert body["average_order"] == "3666", body
            assert body["top_products"][0]["amount"] == "3333", body["top_products"]
            for field in ("gross_sales", "tax", "net_sales", "average_order", "discounts", "net_after_refunds"):
                assert Decimal(body[field]) == Decimal(body[field]).to_integral_value(), (field, body[field])
    finally:
        await cleanup_company(company_id, [email] if email else [])
