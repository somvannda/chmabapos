"""A refund is paid in the store's currency, and the drawer agrees.

A USD store may take a riel cash tender (the customer pays 40,000 KHR for a $10
sale at 4,000). What the refund returns is a decision, and the code makes it
silently: the refund is denominated in the order's currency - the store's - and
the drawer counts the converted base amount on both sides.

This pins that decision so a future change to tender-level refunds cannot quietly
start subtracting 40,000 from a 10.00 drawer.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_a_riel_tender_is_refunded_in_the_store_currency_and_the_drawer_balances() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Dual Tender Co", "Main", plan="pro", email_prefix="refund-tender")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]

            enabled = await client.put(
                "/api/v1/settings/currencies", headers=headers, json={"primary_code": "USD", "enabled_codes": ["USD", "KHR"]}
            )
            assert enabled.status_code == 200, enabled.text
            configured = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"currency_code": "USD", "service_tax_rate": 0}
            )
            assert configured.status_code == 200, configured.text
            rate = await client.post(
                "/api/v1/exchange-rates",
                headers=headers,
                json={"base_currency_code": "USD", "quote_currency_code": "KHR", "rate": "4000", "is_active": True},
            )
            assert rate.status_code in (200, 201), rate.text

            shift = await client.post("/api/v1/shifts/open", headers=store_headers, json={"opening_float": "0"})
            assert shift.status_code == 201, shift.text

            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={"name": "Dual Item", "sku": f"DUAL-{uuid.uuid4().hex[:8]}", "price": "10.00", "category_id": category_id, "opening_stock": 5},
                )
            ).json()
            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product["id"], "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "KHR", "amount": "40000"}],
                },
            )
            assert order.status_code == 201, order.text
            body = order.json()
            assert body["currency_code"] == "USD", body
            assert Decimal(body["total"]) == Decimal("10"), body

            refund = await client.post(
                f"/api/v1/orders/{body['id']}/refund",
                headers=store_headers,
                json={"method": "cash", "items": [{"product_id": product["id"], "quantity": 1}]},
            )
            assert refund.status_code == 201, refund.text
            refunded = refund.json()

            # The refund is in the store's currency - not the 40,000 riel the
            # customer handed over.
            assert refunded["currency_code"] == "USD", refunded
            assert Decimal(refunded["total"]) == Decimal("10"), refunded

            closed = await client.post(
                f"/api/v1/shifts/{shift.json()['id']}/close", headers=store_headers, json={"counted_cash": "0"}
            )
            assert closed.status_code == 200, closed.text
            drawer = closed.json()
            # Both sides are the converted base amount, so an empty drawer reconciles.
            assert drawer["cash_received"] == "10.00", drawer
            assert drawer["cash_refunds"] == "10.00", drawer
            assert drawer["expected_cash"] == "0.00", drawer
    finally:
        await cleanup_company(company_id, [email] if email else [])
