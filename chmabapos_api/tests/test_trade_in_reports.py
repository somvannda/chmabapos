from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_trade_in_value_appears_in_the_summary_report() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Trade-in Reports", "Main", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Galaxy S22 (used)", "sku": f"TRP-{uuid.uuid4().hex[:8]}", "price": "600.00", "category_id": category_id, "opening_stock": 0},
            )
            product_id = product.json()["id"]
            created = await client.post(
                "/api/v1/trade-ins",
                headers=store_headers,
                json={"product_id": product_id, "serial_number": f"TRP-{uuid.uuid4().hex[:8]}", "assessed_value": "250.00"},
            )
            assert created.status_code == 201, created.text

            summary = (await client.get("/api/v1/reports/summary", headers=store_headers)).json()
            assert summary["trade_in_value"] == "250.00"
            assert summary["trade_in_count"] == 1

            # A voided trade-in drops out of the intake total.
            await client.post(f"/api/v1/trade-ins/{created.json()['id']}/void", headers=store_headers)
            after = (await client.get("/api/v1/reports/summary", headers=store_headers)).json()
            assert after["trade_in_value"] == "0.00"
            assert after["trade_in_count"] == 0
    finally:
        await cleanup_company(company_id, [email] if email else [])
