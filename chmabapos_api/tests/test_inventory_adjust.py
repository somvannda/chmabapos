from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _setup_store(client: AsyncClient) -> dict[str, str]:
    """Register an owner, verify, sign in and open a paid starter workspace."""
    email = f"adjust-reason-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Adjust Reason", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Adjust Reason Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    return {**headers, "X-Store-ID": setup.json()["store"]["id"]}


async def _audit_details(client: AsyncClient, headers: dict[str, str], action: str) -> list[dict]:
    response = await client.get("/api/v1/audit-logs", headers=headers)
    assert response.status_code == 200, response.text
    return [row["details"] for row in response.json() if row["action"] == action]


@pytest.mark.asyncio
async def test_adjusting_a_product_records_the_reason() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product = await client.post(
            "/api/v1/products",
            headers=headers,
            json={"name": "Reason Laptop", "sku": f"RL-{uuid.uuid4().hex[:8]}", "price": "500.00", "opening_stock": 5},
        )
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]

        adjusted = await client.patch(
            f"/api/v1/inventory/{product_id}",
            headers=headers,
            json={"quantity": 2, "reason": "correct miscount"},
        )
        assert adjusted.status_code == 200, adjusted.text

        details = await _audit_details(client, headers, "inventory_adjusted")
        assert any(entry.get("reason") == "correct miscount" and entry.get("quantity") == "2" for entry in details), details


@pytest.mark.asyncio
async def test_adjusting_a_variant_records_the_variant_and_reason() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product = await client.post(
            "/api/v1/products",
            headers=headers,
            json={"name": "Reason Phone", "sku": f"RP-{uuid.uuid4().hex[:8]}", "price": "100.00"},
        )
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]
        variants = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [{"sku": f"RV-{uuid.uuid4().hex[:6]}", "name": "Space Gray", "opening_stock": 4}]},
        )
        assert variants.status_code == 200, variants.text
        variant_id = variants.json()["variants"][0]["id"]

        adjusted = await client.patch(
            f"/api/v1/inventory/{product_id}",
            headers=headers,
            json={"quantity": 3, "reason": "found in back room", "variant_id": variant_id},
        )
        assert adjusted.status_code == 200, adjusted.text

        details = await _audit_details(client, headers, "inventory_adjusted")
        assert any(entry.get("reason") == "found in back room" and entry.get("variant") == "Space Gray" for entry in details), details


@pytest.mark.asyncio
async def test_a_no_op_adjustment_does_not_write_an_audit_entry() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product = await client.post(
            "/api/v1/products",
            headers=headers,
            json={"name": "Same Count", "sku": f"SC-{uuid.uuid4().hex[:8]}", "price": "10.00", "opening_stock": 5},
        )
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]

        unchanged = await client.patch(
            f"/api/v1/inventory/{product_id}",
            headers=headers,
            json={"quantity": 5, "reason": "no change"},
        )
        assert unchanged.status_code == 200, unchanged.text

        details = await _audit_details(client, headers, "inventory_adjusted")
        assert all(entry.get("reason") != "no change" for entry in details), details
