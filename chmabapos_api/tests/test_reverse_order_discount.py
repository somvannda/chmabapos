"""A provider-initiated reversal must return the discounted amount actually paid."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import _system_reverse_order, order_by_id
from app.db import SessionLocal
from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_system_reverse_order_refunds_the_discounted_amount() -> None:
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Reverse Discount Store", "Main", plan="starter", email_prefix="rev-disc")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Reverse Item", "sku": f"REV-{uuid.uuid4().hex[:8]}", "price": "100.00", "opening_stock": 10},
            )
            product_id = product.json()["id"]

            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 2}], "discount": "40.00", "payment_method": "cash"},
            )
            assert order.status_code == 201, order.text
            order_body = order.json()
            assert Decimal(order_body["total"]) == Decimal("176.00")  # 200 - 40 + 10% tax

            # Simulate the provider reversal path directly (the webhook calls this).
            async with SessionLocal() as db:
                loaded = await order_by_id(db, uuid.UUID(order_body["id"]))
                await _system_reverse_order(db, loaded)
                await db.commit()

            refunds = (await client.get(f"/api/v1/orders/{order_body['id']}/refunds", headers=store_headers)).json()
            assert refunds
            # The reversal must not hand back the undiscounted subtotal plus tax.
            assert Decimal(refunds[0]["total"]) == Decimal(order_body["total"])
            assert Decimal(refunds[0]["total"]) != Decimal("220.00")

            refreshed = await client.get(f"/api/v1/orders/{order_body['id']}", headers=store_headers)
            assert refreshed.json()["status"] == "refunded"
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
