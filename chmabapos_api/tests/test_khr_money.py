"""A KHR sale must stay in whole riel through tax and totals.

The visible "4000.00" was only the API's Decimal column: both clients already
format KHR with no decimals. The risk that remains is arithmetic - a tax or total
with a fractional riel, which no formatter can undo. This drives a real KHR
checkout with a tax rate that does not divide evenly and asserts every figure is a
whole number of riel.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


def _whole(value: str | int | Decimal) -> bool:
    return Decimal(str(value)) == Decimal(str(value)).to_integral_value()


@pytest.mark.asyncio
async def test_a_khr_sale_rounds_tax_and_total_to_whole_riel() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Riel Math Co", "Main", plan="pro", email_prefix="khr-math")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_id = ctx["headers"], ctx["store_id"]

            currencies = await client.put(
                "/api/v1/settings/currencies", headers=headers, json={"primary_code": "USD", "enabled_codes": ["USD", "KHR"]}
            )
            assert currencies.status_code == 200, currencies.text
            configured = await client.patch(
                f"/api/v1/stores/{store_id}", headers=headers, json={"currency_code": "KHR", "service_tax_rate": 10}
            )
            assert configured.status_code == 200, configured.text

            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            # 3,333 at 10% is 333.3 - a fractional riel that must be rounded, not kept.
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={"name": "Odd Riel", "sku": f"KH-{uuid.uuid4().hex[:8]}", "price": "3333", "category_id": category_id, "opening_stock": 5},
                )
            ).json()

            order = await client.post(
                "/api/v1/orders",
                headers=ctx["store_headers"],
                json={
                    "items": [{"product_id": product["id"], "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "KHR", "amount": "3700"}],
                },
            )
            assert order.status_code == 201, order.text
            body = order.json()

            assert Decimal(body["subtotal"]) == Decimal("3333"), body
            assert _whole(body["tax"]), f"tax has a fractional riel: {body['tax']}"
            assert Decimal(body["tax"]) == Decimal("333"), body
            assert _whole(body["total"]), f"total has a fractional riel: {body['total']}"
            assert Decimal(body["total"]) == Decimal("3666"), body
    finally:
        await cleanup_company(company_id, [email] if email else [])
