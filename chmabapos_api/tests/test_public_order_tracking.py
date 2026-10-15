"""Public order tracking.

A customer who placed an order can follow it with an unguessable token, and sees
only their own ticket. The point of these tests is as much what is *absent* as
what is present.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _public_store_with_product(client: AsyncClient, suffix: str) -> tuple[dict, str]:
    ctx = await register_and_setup(client, f"Track Co {suffix}", f"Desk {suffix}", email_prefix="track")
    category_id = (await client.get("/api/v1/categories", headers=ctx["headers"])).json()[0]["id"]
    await client.post(
        "/api/v1/products",
        headers=ctx["store_headers"],
        json={
            "name": "Tracked Latte",
            "sku": f"TK-{suffix}",
            "price": "5.00",
            "category_id": category_id,
            "opening_stock": 10,
        },
    )
    enabled = await client.patch(
        f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
    )
    return ctx, enabled.json()["token"]


@pytest.mark.asyncio
async def test_a_customer_can_follow_their_own_order() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx, store_token = await _public_store_with_product(client, suffix)
            email, company_id = ctx["email"], ctx["company_id"]
            product_id = (await client.get("/api/v1/products", headers=ctx["store_headers"])).json()[0]["id"]

            submitted = await client.post(
                f"/api/v1/public/order/{store_token}",
                json={"items": [{"product_id": product_id, "quantity": 2}], "customer_name": "Sokha"},
            )
            assert submitted.status_code == 201, submitted.text
            order = submitted.json()

            # A public submission carries a token, and it is not the row id - an
            # enumerable id in a public URL would expose other customers' orders.
            assert order["public_token"], order
            assert order["public_token"] != str(order["id"])

            status = await client.get(f"/api/v1/public/orders/{order['public_token']}")
            assert status.status_code == 200, status.text
            body = status.json()
            assert body["store_name"] == f"Desk {suffix}"
            assert body["status"] == "open"
            assert body["currency_code"] == "USD"
            # The figure matches what the till would charge, because it comes from
            # the same helper rather than a second implementation.
            assert body["total"] == order["total"]

            # Nothing personal, and no internal identifiers.
            for leaked in ("customer_name", "customer_email", "customer_note", "id", "store_id", "items"):
                assert leaked not in body, f"{leaked} must not be exposed"

            # An unknown token is a 404, and says nothing about whether one exists.
            missing = await client.get("/api/v1/public/orders/not-a-real-token")
            assert missing.status_code == 404, missing.text
            assert "not found" in missing.json()["detail"].lower()
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_tokens_do_not_expose_another_order() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx, store_token = await _public_store_with_product(client, suffix)
            email, company_id = ctx["email"], ctx["company_id"]
            product_id = (await client.get("/api/v1/products", headers=ctx["store_headers"])).json()[0]["id"]

            def body(quantity: int) -> dict:
                return {"items": [{"product_id": product_id, "quantity": quantity}]}

            first = (await client.post(f"/api/v1/public/order/{store_token}", json=body(1))).json()
            second = (await client.post(f"/api/v1/public/order/{store_token}", json=body(3))).json()

            assert first["public_token"] != second["public_token"]

            # Each token resolves to its own ticket, not to whichever came last.
            first_status = (await client.get(f"/api/v1/public/orders/{first['public_token']}")).json()
            assert first_status["total"] == first["total"]
            assert first_status["total"] != second["total"]
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
