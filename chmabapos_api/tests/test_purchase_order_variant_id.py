"""The purchase-order dialog must be able to pick a variant from /inventory.

It reads the variant id out of the inventory payload. That payload names the
field ``variant_id``; when the dialog read ``variant.id`` instead it sent
``"undefined"`` as the variant and the API answered a bare 500 (a ValueError
from ``UUID()``). These tests pin the contract and the failure message.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _setup_store(client: AsyncClient) -> dict[str, str]:
    email = f"po-variant-id-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "PO Variant Id", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "PO Variant Id Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    return {**headers, "X-Store-ID": setup.json()["store"]["id"]}


async def _product_with_variant(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    product = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Variant Laptop", "sku": f"VL-{uuid.uuid4().hex[:8]}", "price": "1200.00"},
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    variants = await client.put(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"variants": [{"sku": f"VL-512-{uuid.uuid4().hex[:6]}", "name": "512GB"}]},
    )
    assert variants.status_code == 200, variants.text
    return product_id, variants.json()["variants"][0]["id"]


@pytest.mark.asyncio
async def test_inventory_names_the_variant_id_field_the_dialog_reads() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variant_id = await _product_with_variant(client, headers)

        inventory = (await client.get("/api/v1/inventory", headers=headers)).json()
        row = next(item for item in inventory if item["product_id"] == product_id)
        variant = row["variants"][0]

        # The dialog must read this field. `id` is deliberately absent, which is
        # what made ``variant.id`` evaluate to undefined in the browser.
        assert variant["variant_id"] == variant_id
        assert "id" not in variant


@pytest.mark.asyncio
async def test_a_malformed_variant_id_is_a_client_error_not_a_500() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, _variant_id = await _product_with_variant(client, headers)

        broken = await client.post(
            "/api/v1/purchases",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": "undefined", "quantity": 1}]},
        )
        assert broken.status_code == 400, broken.text
        assert "variant" in broken.json()["detail"].lower()

        bad_product = await client.post(
            "/api/v1/purchases",
            headers=headers,
            json={"items": [{"product_id": "undefined", "quantity": 1}]},
        )
        assert bad_product.status_code == 400, bad_product.text


@pytest.mark.asyncio
async def test_the_variant_id_the_inventory_payload_returns_creates_the_order() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, _variant_id = await _product_with_variant(client, headers)

        inventory = (await client.get("/api/v1/inventory", headers=headers)).json()
        row = next(item for item in inventory if item["product_id"] == product_id)
        variant_id = row["variants"][0]["variant_id"]

        created = await client.post(
            "/api/v1/purchases",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 1, "unit_cost": "900.00"}]},
        )
        assert created.status_code == 201, created.text
        assert created.json()["items"][0]["variant_id"] == variant_id
