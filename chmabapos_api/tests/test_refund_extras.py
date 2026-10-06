"""A full refund/void reverses the whole sale: tip, loyalty points and batches."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _setup(client: AsyncClient):
    ctx = await register_and_setup(client, "Refund Extras Store", "Main", plan="starter", email_prefix="refund-extra")
    headers, store_headers = ctx["headers"], ctx["store_headers"]
    await client.patch(
        f"/api/v1/stores/{ctx['store_id']}",
        headers=headers,
        json={"preferences": {"allow_tip": True, "loyalty_enabled": True, "loyalty_pts_per_usd": 1}},
    )
    product = (
        await client.post("/api/v1/products", headers=store_headers, json={"name": "Batch Item", "sku": f"BX-{uuid.uuid4().hex[:8]}", "price": "10.00", "opening_stock": 10})
    ).json()
    await client.post(f"/api/v1/products/{product['id']}/batches", headers=store_headers, json={"batches": [{"quantity_on_hand": 10}]})
    customer = (await client.post("/api/v1/customers", headers=headers, json={"name": "Loyal Buyer", "email": f"loyal-{uuid.uuid4().hex[:8]}@example.com"})).json()
    return ctx, headers, store_headers, product["id"], customer["id"]


async def _points(client, headers, customer_id) -> Decimal:
    data = (await client.get(f"/api/v1/customers/{customer_id}", headers=headers)).json()
    if isinstance(data, dict) and "customer" in data:
        return Decimal(str(data["customer"]["points"]))
    return Decimal(str(data["points"]))


async def _batch_total(client, store_headers, product_id) -> float:
    batches = (await client.get(f"/api/v1/products/{product_id}/batches", headers=store_headers)).json()
    return sum(float(batch["quantity_on_hand"]) for batch in batches)


@pytest.mark.asyncio
async def test_full_refund_returns_tip_and_reverses_points_and_batches() -> None:
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx, headers, store_headers, product_id, customer_id = await _setup(client)
            email, company_id = ctx["email"], ctx["company_id"]

            order = (
                await client.post(
                    "/api/v1/orders",
                    headers=store_headers,
                    json={"items": [{"product_id": product_id, "quantity": 2}], "customer_id": customer_id, "tip": "3.00", "payment_method": "cash"},
                )
            ).json()
            assert order["status"] == "paid"
            assert float(order["tip"]) == 3.0

            assert await _points(client, headers, customer_id) > 0
            assert await _batch_total(client, store_headers, product_id) == 8

            refund = (
                await client.post(f"/api/v1/orders/{order['id']}/refund", headers=store_headers, json={"method": "cash", "items": [{"product_id": product_id, "quantity": 2}]})
            ).json()
            # A full refund returns the tip: the refunded total matches what was paid.
            assert Decimal(str(refund["total"])) == Decimal(str(order["total"]))
            # Loyalty points the sale awarded are clawed back, and batches restored.
            assert await _points(client, headers, customer_id) == 0
            assert await _batch_total(client, store_headers, product_id) == 10
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_partial_refund_leaves_tip_points_and_batches() -> None:
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx, headers, store_headers, product_id, customer_id = await _setup(client)
            email, company_id = ctx["email"], ctx["company_id"]

            order = (
                await client.post(
                    "/api/v1/orders",
                    headers=store_headers,
                    json={"items": [{"product_id": product_id, "quantity": 4}], "customer_id": customer_id, "tip": "3.00", "payment_method": "cash"},
                )
            ).json()
            points_after_sale = await _points(client, headers, customer_id)
            assert await _batch_total(client, store_headers, product_id) == 6

            refund = (
                await client.post(f"/api/v1/orders/{order['id']}/refund", headers=store_headers, json={"method": "cash", "items": [{"product_id": product_id, "quantity": 2}]})
            ).json()
            # Partial refund: no tip returned, points untouched, batch untouched
            # (only the product balance is restored).
            assert Decimal(str(refund["total"])) < Decimal(str(order["total"]))
            assert await _points(client, headers, customer_id) == points_after_sale
            assert await _batch_total(client, store_headers, product_id) == 6
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
