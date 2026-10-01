from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _setup_store(client: AsyncClient) -> dict[str, str]:
    """Register an owner, verify, sign in and open a paid starter workspace."""
    email = f"po-variant-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "PO Variant Test", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "PO Variant Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    return {**headers, "X-Store-ID": setup.json()["store"]["id"]}


async def _product_with_variant(client: AsyncClient, headers: dict[str, str], *, track_serials: bool = False) -> tuple[str, str]:
    product = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "PO Phone", "sku": f"PO-{uuid.uuid4().hex[:8]}", "price": "100.00", "track_serials": track_serials},
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    variants = await client.put(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"variants": [{"sku": f"PO-128-{uuid.uuid4().hex[:6]}", "name": "128GB"}]},
    )
    assert variants.status_code == 200, variants.text
    return product_id, variants.json()["variants"][0]["id"]


@pytest.mark.asyncio
async def test_purchase_order_requires_and_receives_by_variant() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variant_id = await _product_with_variant(client, headers)

        # A product sold in variants must be ordered by variant.
        missing = await client.post("/api/v1/purchases", headers=headers, json={"items": [{"product_id": product_id, "quantity": 2}]})
        assert missing.status_code == 400, missing.text

        created = await client.post(
            "/api/v1/purchases",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 2, "unit_cost": "12.00"}]},
        )
        assert created.status_code == 201, created.text
        assert created.json()["items"][0]["variant_id"] == variant_id

        received = await client.post(f"/api/v1/purchases/{created.json()['id']}/receive", headers=headers)
        assert received.status_code == 200, received.text

        inventory = (await client.get("/api/v1/inventory", headers=headers)).json()
        row = next(item for item in inventory if item["product_id"] == product_id)
        variant = next(item for item in row["variants"] if item["variant_id"] == variant_id)
        assert variant["on_hand"] == 2


@pytest.mark.asyncio
async def test_receiving_a_serial_tracked_product_from_a_po_is_rejected() -> None:
    """Serials must come through the stock flow so each unit keeps its number."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variant_id = await _product_with_variant(client, headers, track_serials=True)
        created = await client.post(
            "/api/v1/purchases",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 1}]},
        )
        assert created.status_code == 201, created.text
        received = await client.post(f"/api/v1/purchases/{created.json()['id']}/receive", headers=headers)
        assert received.status_code == 400, received.text
