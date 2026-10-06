"""Redeem loyalty points at checkout; restore them on a full refund."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _points(client, headers, customer_id) -> int:
    data = (await client.get(f"/api/v1/customers/{customer_id}", headers=headers)).json()
    customer = data.get("customer") if isinstance(data, dict) and "customer" in data else data
    return int(Decimal(str(customer["points"])))


@pytest.mark.asyncio
async def test_redeem_points_at_checkout_and_restore_on_full_refund() -> None:
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Loyalty Redeem Store", "Main", plan="starter", email_prefix="loyalty-redeem")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"preferences": {"loyalty_enabled": True, "loyalty_pts_per_usd": 1}})
            product = (await client.post("/api/v1/products", headers=store_headers, json={"name": "Redeem Item", "sku": f"RD-{uuid.uuid4().hex[:8]}", "price": "100.00", "opening_stock": 5})).json()
            customer = (await client.post("/api/v1/customers", headers=headers, json={"name": "Points Buyer", "email": f"points-{uuid.uuid4().hex[:8]}@example.com"})).json()
            assert (await client.patch(f"/api/v1/customers/{customer['id']}/points", headers=headers, json={"delta": 100})).status_code == 200

            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product["id"], "quantity": 1}], "customer_id": customer["id"], "redeem_points": 40, "payment_method": "cash"},
            )
            assert order.status_code == 201, order.text
            body = order.json()
            assert Decimal(str(body["discount"])) == Decimal("40.00")
            assert Decimal(str(body["total"])) == Decimal("66.00")  # (100 - 40) + 10% tax

            # 100 granted - 40 redeemed + 66 earned = 126.
            assert await _points(client, headers, customer["id"]) == 126

            # Redeeming more than the balance is refused.
            over = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product["id"], "quantity": 1}], "customer_id": customer["id"], "redeem_points": 100000, "payment_method": "cash"},
            )
            assert over.status_code == 409, over.text

            refund = await client.post(f"/api/v1/orders/{body['id']}/refund", headers=store_headers, json={"method": "cash", "items": [{"product_id": product["id"], "quantity": 1}]})
            assert refund.status_code == 201, refund.text
            # Full refund: claw back the 66 earned and return the 40 redeemed -> 100.
            assert await _points(client, headers, customer["id"]) == 100
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
