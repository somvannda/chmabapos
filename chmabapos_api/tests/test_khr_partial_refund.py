"""A partial KHR refund is whole riel.

A refund prorates the order's tax by the refunded share of the subtotal. On an
even split that lands on a whole riel by luck; on an uneven one it does not, and
the customer is handed 3666.50 - a sum the drawer cannot make.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_a_partial_khr_refund_is_whole_riel() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Riel Refund Co", "Main", plan="pro", email_prefix="khr-partial-refund")
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
                    json={"name": "Split Item", "sku": f"SPL-{uuid.uuid4().hex[:8]}", "price": "3333", "category_id": category_id, "opening_stock": 5},
                )
            ).json()
            # Two units: subtotal 6,666, tax 666.6 -> 667, total 7,333. Refunding one
            # unit leaves half the tax, 333.5 - the fractional case.
            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product["id"], "quantity": 2}],
                    "tenders": [{"method": "cash", "currency_code": "KHR", "amount": "7333"}],
                },
            )
            assert order.status_code == 201, order.text
            assert order.json()["total"] == "7333", order.json()

            refund = await client.post(
                f"/api/v1/orders/{order.json()['id']}/refund",
                headers=store_headers,
                json={"method": "cash", "items": [{"product_id": product["id"], "quantity": 1}]},
            )
            assert refund.status_code == 201, refund.text
            body = refund.json()

            assert body["currency_code"] == "KHR", body
            for field in ("subtotal", "tax", "total"):
                assert Decimal(body[field]) == Decimal(body[field]).to_integral_value(), (field, body[field])
            assert body["total"] == "3667", body
    finally:
        await cleanup_company(company_id, [email] if email else [])
