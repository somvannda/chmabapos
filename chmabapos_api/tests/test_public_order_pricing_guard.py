"""A public order never takes a price from the request.

The add-on feature shipped with exactly that hole: the submit summed
``entry.price_delta`` from the payload, so anyone could send ``-100`` and discount
their own order. It is fixed, but the guard lived in one test for one endpoint.

This drives hostile money at **both** order endpoints - the slug storefront and the
legacy token link - so a field added to the payload later is covered by intent
rather than by luck.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup

HOSTILE = [
    "-100.00",
    "-0.01",
    "999999.99",
    "0",
    "",
    "not-a-number",
]


@pytest.mark.asyncio
async def test_public_orders_ignore_a_price_from_the_request() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Pricing Store", "Main", plan="pro", email_prefix="pricing")
            email, company_id = ctx["email"], ctx["company_id"]
            group = (
                await client.post(
                    "/api/v1/modifier-groups",
                    headers=ctx["headers"],
                    json={"name": "Milk", "min_select": 0, "max_select": 1, "modifiers": [{"name": "Oat", "price_delta": "0.50"}]},
                )
            ).json()
            category_id = (await client.get("/api/v1/categories", headers=ctx["headers"])).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={"name": "Priced Latte", "sku": f"PR-{uuid.uuid4().hex[:8]}", "price": "3.00", "category_id": category_id, "opening_stock": 100, "modifier_group_id": group["id"]},
                )
            ).json()
            settings = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            store_token = settings.json()["token"]
            current = (await client.get("/api/v1/workspaces/current", headers=ctx["store_headers"])).json()
            slug_endpoint = f"/api/v1/public/store/{current['company']['slug']}/{current['store']['slug']}/orders"
            legacy_endpoint = f"/api/v1/public/order/{store_token}"

            for endpoint in (slug_endpoint, legacy_endpoint):
                # A lying price is ignored: the catalogue's 0.50 is applied, not the
                # caller's number. Anything else means a public endpoint is trusting
                # the request with money.
                for hostile in HOSTILE:
                    response = await client.post(
                        endpoint,
                        json={"items": [{"product_id": product["id"], "quantity": 1, "modifiers": [{"name": "Oat", "price_delta": hostile}]}]},
                    )
                    # A malformed delta may be refused at the boundary (422); what it
                    # must never do is succeed at the caller's price.
                    assert response.status_code in (201, 422), f"{endpoint} / {hostile!r} -> {response.status_code} {response.text}"
                    if response.status_code == 201:
                        line = response.json()["items"][0]
                        assert line["unit_price"] == "3.50", f"{endpoint} / {hostile!r} priced at {line['unit_price']}"
                        assert line["modifiers"][0]["price_delta"] == "0.50"

                # Quantity is the caller's to choose, but never forbidden values, and
                # never beyond the shelf.
                for bad_quantity in (0, -1):
                    rejected = await client.post(endpoint, json={"items": [{"product_id": product["id"], "quantity": bad_quantity}]})
                    assert rejected.status_code == 422, f"{endpoint} / qty {bad_quantity} -> {rejected.status_code}"

                beyond_stock = await client.post(endpoint, json={"items": [{"product_id": product["id"], "quantity": 9999}]})
                assert beyond_stock.status_code == 409, f"{endpoint} / qty 9999 -> {beyond_stock.status_code}"
    finally:
        await cleanup_company(company_id, [email] if email else [])
