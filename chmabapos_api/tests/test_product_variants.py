from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _setup_store(client: AsyncClient) -> dict[str, str]:
    """Register an owner, verify, sign in and open a paid starter workspace."""
    email = f"variants-test-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Variants Test", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Variants Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    return {**headers, "X-Store-ID": setup.json()["store"]["id"]}


async def _create_product(client: AsyncClient, headers: dict[str, str]) -> str:
    product = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Variant Phone", "sku": f"VP-{uuid.uuid4().hex[:8]}", "price": "100.00"},
    )
    assert product.status_code == 201, product.text
    return product.json()["id"]


@pytest.mark.asyncio
async def test_adds_a_second_variant_alongside_an_existing_one() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id = await _create_product(client, headers)

        first = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [{"sku": "VP-128", "name": "128GB"}]},
        )
        assert first.status_code == 200, first.text
        variant_id = first.json()["variants"][0]["id"]

        second = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [
                {"id": variant_id, "sku": "VP-128", "name": "128GB"},
                {"sku": "VP-256", "name": "256GB"},
            ]},
        )
        assert second.status_code == 200, second.text
        assert sorted(v["name"] for v in second.json()["variants"]) == ["128GB", "256GB"]


@pytest.mark.asyncio
async def test_reusing_a_removed_variants_sku_in_one_save_is_allowed() -> None:
    """Removing a variant and re-adding its SKU must not conflict with itself."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id = await _create_product(client, headers)

        created = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [{"sku": "REUSE-1", "name": "Old"}]},
        )
        assert created.status_code == 200, created.text

        replaced = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [{"sku": "REUSE-1", "name": "New"}]},
        )
        assert replaced.status_code == 200, replaced.text
        body = replaced.json()["variants"]
        assert len(body) == 1
        assert body[0]["name"] == "New"


@pytest.mark.asyncio
async def test_a_missing_id_is_resolved_by_sku_instead_of_conflicting() -> None:
    """A stale client that drops the id still edits the matching variant."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id = await _create_product(client, headers)

        created = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [{"sku": "STALE-1", "name": "Old"}]},
        )
        assert created.status_code == 200, created.text

        renamed = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [
                {"sku": "STALE-1", "name": "Old"},
                {"sku": "STALE-2", "name": "Second"},
            ]},
        )
        assert renamed.status_code == 200, renamed.text
        assert sorted(v["name"] for v in renamed.json()["variants"]) == ["Old", "Second"]


@pytest.mark.asyncio
async def test_duplicate_skus_in_one_payload_return_a_clear_409() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id = await _create_product(client, headers)

        response = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [{"sku": "DUP-1", "name": "A"}, {"sku": "DUP-1", "name": "B"}]},
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == "Variant SKU already exists: DUP-1"


@pytest.mark.asyncio
async def test_swapping_skus_between_variants_conflicts_instead_of_erroring() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id = await _create_product(client, headers)

        created = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [{"sku": "SW-A", "name": "A"}, {"sku": "SW-B", "name": "B"}]},
        )
        assert created.status_code == 200, created.text
        ids = {variant["name"]: variant["id"] for variant in created.json()["variants"]}

        swapped = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [
                {"id": ids["A"], "sku": "SW-B", "name": "A"},
                {"id": ids["B"], "sku": "SW-A", "name": "B"},
            ]},
        )
        assert swapped.status_code == 409, swapped.text
