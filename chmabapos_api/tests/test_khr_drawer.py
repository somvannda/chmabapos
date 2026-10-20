"""A KHR drawer is counted in whole riel.

A shift report is the figure a cashier is measured against and a manager signs off,
so it must be in the store's own currency - and a riel has no subunit. The figures
were quantised to two decimals regardless, so a KHR Z-report said 103666.00.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_a_khr_shift_closes_in_whole_riel() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Riel Drawer Co", "Main", plan="pro", email_prefix="khr-drawer")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]

            enabled = await client.put(
                "/api/v1/settings/currencies", headers=headers, json={"primary_code": "USD", "enabled_codes": ["USD", "KHR"]}
            )
            assert enabled.status_code == 200, enabled.text
            configured = await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"currency_code": "KHR"})
            assert configured.status_code == 200, configured.text

            opened = await client.post("/api/v1/shifts/open", headers=store_headers, json={"opening_float": "100000"})
            assert opened.status_code == 201, opened.text

            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={"name": "Drawer Item", "sku": f"DRW-{uuid.uuid4().hex[:8]}", "price": "3333", "category_id": category_id, "opening_stock": 5},
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

            closed = await client.post(
                f"/api/v1/shifts/{opened.json()['id']}/close", headers=store_headers, json={"counted_cash": "103666"}
            )
            assert closed.status_code == 200, closed.text
            body = closed.json()

            # These are strings on the wire; 103666.00 is the same number but the
            # wrong statement about a currency with no hundredths.
            assert body["cash_received"] == "3666", body
            assert body["sales_total"] == "3666", body
            assert body["expected_cash"] == "103666", body
            assert body["difference"] == "0", body
            assert Decimal(body["expected_cash"]) == Decimal("103666")
    finally:
        await cleanup_company(company_id, [email] if email else [])
