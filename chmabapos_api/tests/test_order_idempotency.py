"""Offline replay: a repeated POST /orders with the same client_order_id is a no-op."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_order_creation_is_idempotent_with_a_client_order_id() -> None:
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Offline Store", "Main", plan="starter", email_prefix="offline")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product = (await client.post("/api/v1/products", headers=store_headers, json={"name": "Offline Item", "sku": f"OF-{uuid.uuid4().hex[:8]}", "price": "5.00", "opening_stock": 10})).json()
            body = {"items": [{"product_id": product["id"], "quantity": 1}], "payment_method": "cash", "client_order_id": f"off-{uuid.uuid4().hex}"}

            first = await client.post("/api/v1/orders", headers=store_headers, json=body)
            assert first.status_code == 201, first.text
            second = await client.post("/api/v1/orders", headers=store_headers, json=body)
            assert second.status_code == 201, second.text
            # The replay returns the original order, not a duplicate.
            assert second.json()["id"] == first.json()["id"]
            assert second.json()["order_number"] == first.json()["order_number"]

            inventory = (await client.get("/api/v1/inventory", headers=store_headers)).json()
            row = next(item for item in inventory if item["product_id"] == product["id"])
            assert row["on_hand"] == 9  # stock was drawn down exactly once
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
