"""Refund math: prorate the captured discount/tax, and only flag the order fully
refunded once every unit has actually been refunded."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _product(client: AsyncClient, headers: dict[str, str], *, price: str, stock: int = 200) -> str:
    created = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": f"Refund Item {uuid.uuid4().hex[:6]}", "sku": f"RFN-{uuid.uuid4().hex[:8]}", "price": price, "opening_stock": stock},
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


@pytest.mark.asyncio
async def test_refund_returns_the_discounted_amount_actually_paid() -> None:
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Refund Discount Store", "Main", plan="starter", email_prefix="refund-disc")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product_id = await _product(client, store_headers, price="100.00")

            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 2}], "discount": "40.00", "payment_method": "cash"},
            )
            assert order.status_code == 201, order.text
            order_body = order.json()
            # 200 subtotal - 40 discount + 10% tax = 176.00 paid.
            assert Decimal(order_body["total"]) == Decimal("176.00")

            refund = await client.post(
                f"/api/v1/orders/{order_body['id']}/refund",
                headers=store_headers,
                json={"method": "cash", "items": [{"product_id": product_id, "quantity": 2}]},
            )
            assert refund.status_code == 201, refund.text
            # A full refund must hand back exactly what was collected, not the
            # undiscounted subtotal plus tax.
            assert Decimal(refund.json()["total"]) == Decimal(order_body["total"])
            assert Decimal(refund.json()["total"]) != Decimal("220.00")

            refreshed = await client.get(f"/api/v1/orders/{order_body['id']}", headers=store_headers)
            assert refreshed.json()["status"] == "refunded"
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_partial_refunds_do_not_flag_the_order_early() -> None:
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Refund Partial Store", "Main", plan="starter", email_prefix="refund-part")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product_id = await _product(client, store_headers, price="1.00")

            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 100}], "payment_method": "cash"},
            )
            assert order.status_code == 201, order.text
            order_id = order.json()["id"]

            for quantity in (50, 45):
                refund = await client.post(
                    f"/api/v1/orders/{order_id}/refund",
                    headers=store_headers,
                    json={"method": "cash", "items": [{"product_id": product_id, "quantity": quantity}]},
                )
                assert refund.status_code == 201, refund.text

            # 95 of 100 units refunded: prior refunds include tax, which must not
            # be treated as pre-tax subtotal progress.
            still_open = await client.get(f"/api/v1/orders/{order_id}", headers=store_headers)
            assert still_open.json()["status"] == "paid"

            final = await client.post(
                f"/api/v1/orders/{order_id}/refund",
                headers=store_headers,
                json={"method": "cash", "items": [{"product_id": product_id, "quantity": 5}]},
            )
            assert final.status_code == 201, final.text
            done = await client.get(f"/api/v1/orders/{order_id}", headers=store_headers)
            assert done.json()["status"] == "refunded"
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
