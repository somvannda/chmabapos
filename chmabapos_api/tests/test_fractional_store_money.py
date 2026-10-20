"""A whole-riel store refuses fractional riel on a discount or a tip.

The client sends these amounts, so nothing stops a KHR till from posting a
discount of 100.50. Rounding it away later hides the mistake and leaves a
fractional figure in the books; the boundary is where to refuse it - the same
place exchange-rate amounts are already checked.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _khr_store_with_item(client: AsyncClient, ctx: dict) -> dict:
    headers, store_headers = ctx["headers"], ctx["store_headers"]
    enabled = await client.put(
        "/api/v1/settings/currencies", headers=headers, json={"primary_code": "USD", "enabled_codes": ["USD", "KHR"]}
    )
    assert enabled.status_code == 200, enabled.text
    configured = await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"currency_code": "KHR", "service_tax_rate": 0})
    assert configured.status_code == 200, configured.text
    category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
    return (
        await client.post(
            "/api/v1/products",
            headers=store_headers,
            json={"name": "Riel Item", "sku": f"FRC-{uuid.uuid4().hex[:8]}", "price": "10000", "category_id": category_id, "opening_stock": 5},
        )
    ).json()


@pytest.mark.asyncio
async def test_a_fractional_riel_discount_is_refused() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Fraction Co", "Main", plan="pro", email_prefix="fraction")
            email, company_id = ctx["email"], ctx["company_id"]
            product = await _khr_store_with_item(client, ctx)

            fractional = await client.post(
                "/api/v1/orders",
                headers=ctx["store_headers"],
                json={"items": [{"product_id": product["id"], "quantity": 1}], "discount": "100.50", "payment_method": "cash"},
            )
            assert fractional.status_code == 400, fractional.text
            assert "Discount must use 0 decimal place(s) for KHR" in fractional.text, fractional.text

            fractional_tip = await client.post(
                "/api/v1/orders",
                headers=ctx["store_headers"],
                json={"items": [{"product_id": product["id"], "quantity": 1}], "tip": "0.50", "payment_method": "cash"},
            )
            assert fractional_tip.status_code == 400, fractional_tip.text
            assert "Tip must use 0 decimal place(s) for KHR" in fractional_tip.text, fractional_tip.text

            whole = await client.post(
                "/api/v1/orders",
                headers=ctx["store_headers"],
                json={"items": [{"product_id": product["id"], "quantity": 1}], "discount": "500", "payment_method": "cash"},
            )
            assert whole.status_code == 201, whole.text
            assert whole.json()["total"] == "9500", whole.json()
    finally:
        await cleanup_company(company_id, [email] if email else [])
