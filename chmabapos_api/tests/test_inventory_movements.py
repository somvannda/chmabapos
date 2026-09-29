from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _setup_store(client: AsyncClient) -> dict[str, str]:
    """Register an owner, verify, sign in and open a paid starter workspace."""
    email = f"movements-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Movements Test", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Movements Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    return {**headers, "X-Store-ID": setup.json()["store"]["id"]}


def _movements_url(**params: str) -> str:
    query = "&".join(f"{key}={value}" for key, value in params.items() if value)
    return f"/api/v1/inventory/movements{'?' + query if query else ''}"


@pytest.mark.asyncio
async def test_movements_list_recent_changes_with_reason_and_actor() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product = await client.post(
            "/api/v1/products",
            headers=headers,
            json={"name": "Movement Laptop", "sku": f"ML-{uuid.uuid4().hex[:8]}", "price": "500.00", "opening_stock": 5},
        )
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]

        restock = await client.post(
            f"/api/v1/inventory/{product_id}/restock",
            headers=headers,
            json={"quantity": 3, "reason": "delivery from supplier", "supplier": "Acme"},
        )
        assert restock.status_code == 200, restock.text

        response = await client.get(_movements_url(product_id=product_id), headers=headers)
        assert response.status_code == 200, response.text
        rows = response.json()

        restock_rows = [row for row in rows if row["movement_type"] == "restock"]
        assert restock_rows and restock_rows[0]["reason"] == "delivery from supplier"
        assert Decimal(restock_rows[0]["quantity"]) == Decimal("3")
        assert restock_rows[0]["product_name"] == "Movement Laptop"
        assert restock_rows[0]["actor"] == "Movements Test"
        # A newer change (the restock) sorts ahead of the opening balance.
        assert rows[0]["movement_type"] == "restock"


@pytest.mark.asyncio
async def test_movements_can_be_filtered_by_variant() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product = await client.post(
            "/api/v1/products",
            headers=headers,
            json={"name": "Movement Phone", "sku": f"MP-{uuid.uuid4().hex[:8]}", "price": "100.00"},
        )
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]
        variants = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [
                {"sku": f"MA-{uuid.uuid4().hex[:6]}", "name": "Space Gray", "opening_stock": 4},
                {"sku": f"MB-{uuid.uuid4().hex[:6]}", "name": "Rose Gold", "opening_stock": 1},
            ]},
        )
        assert variants.status_code == 200, variants.text
        space_gray = next(row for row in variants.json()["variants"] if row["name"] == "Space Gray")["id"]

        response = await client.get(_movements_url(variant_id=space_gray), headers=headers)
        assert response.status_code == 200, response.text
        rows = response.json()
        assert rows, "expected at least the opening balance movement"
        assert all(row["variant_id"] == space_gray for row in rows)
        assert all(row["variant_name"] == "Space Gray" for row in rows)


@pytest.mark.asyncio
async def test_movements_for_an_unknown_product_are_empty() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        # An unknown product id simply returns nothing rather than leaking other products.
        response = await client.get(_movements_url(product_id=str(uuid.uuid4())), headers=headers)
        assert response.status_code == 200, response.text
        assert response.json() == []
