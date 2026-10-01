from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _setup_store(client: AsyncClient) -> dict[str, str]:
    """Register an owner, verify, sign in and open a paid starter workspace."""
    email = f"supplier-price-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Supplier Price Test", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Supplier Price Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    return {**headers, "X-Store-ID": setup.json()["store"]["id"]}


async def _supplier(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post("/api/v1/suppliers", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _product(client: AsyncClient, headers: dict[str, str], name: str = "Priced Phone") -> str:
    response = await client.post("/api/v1/products", headers=headers, json={"name": name, "sku": f"SP-{uuid.uuid4().hex[:8]}", "price": "100.00"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_supplier_prices_are_per_variant() -> None:
    """The same spec from two suppliers gets two rows, not two variants."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id = await _product(client, headers)
        variants = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [{"sku": "SP-128", "name": "128GB"}, {"sku": "SP-256", "name": "256GB"}]},
        )
        assert variants.status_code == 200, variants.text
        first, second = [variant["id"] for variant in variants.json()["variants"]]
        supplier_a = await _supplier(client, headers, "Supplier A")
        supplier_b = await _supplier(client, headers, "Supplier B")

        saved = await client.put(
            f"/api/v1/products/{product_id}/supplier-prices",
            headers=headers,
            json={"prices": [
                {"supplier_id": supplier_a, "variant_id": first, "unit_cost": "10.00", "lead_time_days": 3},
                {"supplier_id": supplier_a, "variant_id": second, "unit_cost": "20.00"},
                {"supplier_id": supplier_b, "variant_id": first, "unit_cost": "9.00", "is_preferred": True},
            ]},
        )
        assert saved.status_code == 200, saved.text
        assert len(saved.json()) == 3

        # A product that has variants must be priced per variant.
        rejected = await client.put(
            f"/api/v1/products/{product_id}/supplier-prices",
            headers=headers,
            json={"prices": [{"supplier_id": supplier_a, "unit_cost": "5.00"}]},
        )
        assert rejected.status_code == 400, rejected.text

        listed = await client.get(f"/api/v1/products/{product_id}/supplier-prices", headers=headers)
        assert listed.status_code == 200, listed.text
        assert {row["supplier_name"] for row in listed.json()} == {"Supplier A", "Supplier B"}


@pytest.mark.asyncio
async def test_supplier_prices_for_product_without_variants() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id = await _product(client, headers, "Single Phone")
        supplier_a = await _supplier(client, headers, "Supplier A")

        saved = await client.put(
            f"/api/v1/products/{product_id}/supplier-prices",
            headers=headers,
            json={"prices": [{"supplier_id": supplier_a, "unit_cost": "12.50"}]},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()[0]["variant_id"] is None

        # The payload is authoritative: an empty set clears the stored rows.
        cleared = await client.put(
            f"/api/v1/products/{product_id}/supplier-prices",
            headers=headers,
            json={"prices": []},
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json() == []
