from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _setup_store(client: AsyncClient) -> dict[str, str]:
    """Register an owner, verify, sign in and open a paid starter workspace."""
    email = f"variant-transfer-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Variant Transfer", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Variant Transfer Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    return {**headers, "X-Store-ID": setup.json()["store"]["id"]}


async def _create_variant_product(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    track_serials: bool = False,
    first_stock: int = 4,
    second_stock: int = 1,
) -> tuple[str, dict[str, str]]:
    """Create a product with two colour variants and return (product_id, name -> variant_id)."""
    product = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "MacBook Test", "sku": f"MB-{uuid.uuid4().hex[:8]}", "price": "500.00", "track_serials": track_serials},
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    variants = await client.put(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"variants": [
            {"sku": f"SG-{uuid.uuid4().hex[:6]}", "name": "Space Gray", "opening_stock": first_stock},
            {"sku": f"RG-{uuid.uuid4().hex[:6]}", "name": "Rose Gold", "opening_stock": second_stock},
        ]},
    )
    assert variants.status_code == 200, variants.text
    return product_id, {row["name"]: row["id"] for row in variants.json()["variants"]}


async def _variant_stock(client: AsyncClient, headers: dict[str, str], product_id: str) -> dict[str, float]:
    rows = await client.get("/api/v1/inventory", headers=headers)
    assert rows.status_code == 200, rows.text
    row = next(item for item in rows.json() if item["product_id"] == product_id)
    return {variant["variant_id"]: variant["on_hand"] for variant in row["variants"]}


@pytest.mark.asyncio
async def test_moving_stock_between_variants_keeps_the_total() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variants = await _create_variant_product(client, headers, first_stock=4, second_stock=1)

        response = await client.post(
            f"/api/v1/inventory/{product_id}/variant-transfer",
            headers=headers,
            json={"from_variant_id": variants["Space Gray"], "to_variant_id": variants["Rose Gold"], "quantity": 3, "reason": "correct miscount"},
        )
        assert response.status_code == 200, response.text

        stock = await _variant_stock(client, headers, product_id)
        assert stock[variants["Space Gray"]] == 1
        assert stock[variants["Rose Gold"]] == 4
        assert sum(stock.values()) == 5


@pytest.mark.asyncio
async def test_moving_more_than_the_source_holds_is_rejected() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variants = await _create_variant_product(client, headers, first_stock=2, second_stock=0)

        response = await client.post(
            f"/api/v1/inventory/{product_id}/variant-transfer",
            headers=headers,
            json={"from_variant_id": variants["Space Gray"], "to_variant_id": variants["Rose Gold"], "quantity": 999},
        )
        assert response.status_code == 409, response.text
        assert "Insufficient stock" in response.json()["detail"]


@pytest.mark.asyncio
async def test_transfer_to_the_same_variant_is_rejected() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variants = await _create_variant_product(client, headers)

        response = await client.post(
            f"/api/v1/inventory/{product_id}/variant-transfer",
            headers=headers,
            json={"from_variant_id": variants["Space Gray"], "to_variant_id": variants["Space Gray"], "quantity": 1},
        )
        assert response.status_code == 400, response.text


@pytest.mark.asyncio
async def test_transfer_with_an_unknown_variant_is_rejected() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variants = await _create_variant_product(client, headers)

        response = await client.post(
            f"/api/v1/inventory/{product_id}/variant-transfer",
            headers=headers,
            json={"from_variant_id": variants["Space Gray"], "to_variant_id": str(uuid.uuid4()), "quantity": 1},
        )
        assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_transfer_is_rejected_for_serial_tracked_products() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variants = await _create_variant_product(client, headers, track_serials=True, first_stock=0, second_stock=0)

        response = await client.post(
            f"/api/v1/inventory/{product_id}/variant-transfer",
            headers=headers,
            json={"from_variant_id": variants["Space Gray"], "to_variant_id": variants["Rose Gold"], "quantity": 1},
        )
        assert response.status_code == 400, response.text


@pytest.mark.asyncio
async def test_transfer_cannot_borrow_another_products_variant() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variants = await _create_variant_product(client, headers)
        _other_id, other_variants = await _create_variant_product(client, headers)

        response = await client.post(
            f"/api/v1/inventory/{product_id}/variant-transfer",
            headers=headers,
            json={"from_variant_id": variants["Space Gray"], "to_variant_id": other_variants["Rose Gold"], "quantity": 1},
        )
        assert response.status_code == 404, response.text
