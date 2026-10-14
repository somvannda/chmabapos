"""Ordering from the slug-addressed storefront.

`POST /public/store/{company_slug}/{store_slug}/orders` is what the storefront
app submits to. It must behave exactly like the tokenised link: same validation,
same pricing, same ticket, and it must not resolve across tenants.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _setup(client: AsyncClient, suffix: str) -> tuple[dict, str, str, str]:
    """A store with one stocked product and online ordering switched on."""
    ctx = await register_and_setup(
        client, f"Order Co {suffix}", f"Counter {suffix}", email_prefix="pub-order"
    )
    category_id = (await client.get("/api/v1/categories", headers=ctx["headers"])).json()[0]["id"]
    product = (
        await client.post(
            "/api/v1/products",
            headers=ctx["store_headers"],
            json={
                "name": "Counter Latte",
                "sku": f"CO-{suffix}",
                "price": "4.00",
                "category_id": category_id,
                "opening_stock": 5,
            },
        )
    )
    assert product.status_code == 201, product.text
    enabled = await client.patch(
        f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
    )
    assert enabled.status_code == 200, enabled.text
    return ctx, f"order-co-{suffix}", f"counter-{suffix}", product.json()["id"]


@pytest.mark.asyncio
async def test_storefront_order_is_accepted_and_reaches_the_staff_board() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx, company_slug, store_slug, product_id = await _setup(client, suffix)
            email, company_id = ctx["email"], ctx["company_id"]
            base = f"/api/v1/public/store/{company_slug}/{store_slug}/orders"

            submitted = await client.post(
                base,
                json={
                    "items": [{"product_id": product_id, "quantity": 2}],
                    "customer_name": "Sokha",
                    "customer_note": "No sugar",
                },
            )
            assert submitted.status_code == 201, submitted.text
            order = submitted.json()

            # The kitchen board is the system of record, so the ticket must be there.
            board = await client.get("/api/v1/held-orders", headers=ctx["store_headers"])
            assert board.status_code == 200, board.text
            assert order["id"] in [row["id"] for row in board.json()]

            # The customer submitted no prices, and none were trusted: the line is
            # priced from the catalogue (2 x 4.00).
            lines = order.get("items") or []
            assert lines, order
            assert lines[0]["unit_price"] == "4.00"
            assert float(lines[0]["quantity"]) == 2
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_storefront_order_rejects_bad_input() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx, company_slug, store_slug, product_id = await _setup(client, suffix)
            email, company_id = ctx["email"], ctx["company_id"]

            # Unknown address, rather than another tenant's store.
            missing = await client.post(
                f"/api/v1/public/store/{company_slug}/nope-{suffix}/orders",
                json={"items": [{"product_id": product_id, "quantity": 1}]},
            )
            assert missing.status_code == 404, missing.text

            # A product that is not this company's.
            foreign = await client.post(
                f"/api/v1/public/store/{company_slug}/{store_slug}/orders",
                json={"items": [{"product_id": str(uuid.uuid4()), "quantity": 1}]},
            )
            assert foreign.status_code == 400, foreign.text

            # More than the shelf holds.
            too_many = await client.post(
                f"/api/v1/public/store/{company_slug}/{store_slug}/orders",
                json={"items": [{"product_id": product_id, "quantity": 99}]},
            )
            assert too_many.status_code == 409, too_many.text
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_storefront_orders_are_refused_when_ordering_is_off() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Closed Co {suffix}", f"Shut {suffix}", email_prefix="pub-order-off"
            )
            email, company_id = ctx["email"], ctx["company_id"]
            category_id = (await client.get("/api/v1/categories", headers=ctx["headers"])).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={
                        "name": "Shut Latte",
                        "sku": f"SH-{suffix}",
                        "price": "3.00",
                        "category_id": category_id,
                        "opening_stock": 5,
                    },
                )
            ).json()

            # Never enabled, so the address does not resolve for ordering.
            response = await client.post(
                f"/api/v1/public/store/closed-co-{suffix}/shut-{suffix}/orders",
                json={"items": [{"product_id": product["id"], "quantity": 1}]},
            )
            assert response.status_code == 404, response.text
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
