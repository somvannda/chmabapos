from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _owner_workspace(client: AsyncClient) -> dict[str, str]:
    email = f"delivery-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Del Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Del Co", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    workspace = setup.json()
    return {**headers, "X-Store-ID": workspace["store"]["id"]}


async def _product(client: AsyncClient, headers: dict[str, str]) -> str:
    product = await client.post("/api/v1/products", headers=headers, json={"name": "Burger", "sku": f"BG-{uuid.uuid4().hex[:8]}", "price": "5.00", "opening_stock": 10})
    assert product.status_code == 201, product.text
    return product.json()["id"]


@pytest.mark.asyncio
async def test_delivery_dispatch_flow() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _owner_workspace(client)
        product_id = await _product(client, headers)
        order = await client.post("/api/v1/orders", headers=headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash", "order_type": "delivery", "customer_name": "Dara"})
        assert order.status_code == 201, order.text
        order_id = order.json()["id"]
        assert order.json()["order_type"] == "delivery"
        assert order.json()["delivery_status"] == "none"

        assigned = await client.patch(f"/api/v1/orders/{order_id}/delivery", headers=headers, json={"status": "assigned", "driver_name": "Sok", "delivery_address": "12 Street 1"})
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["delivery_status"] == "assigned"
        assert assigned.json()["driver_name"] == "Sok"
        assert assigned.json()["assigned_at"] is not None

        delivered = await client.patch(f"/api/v1/orders/{order_id}/delivery", headers=headers, json={"status": "delivered"})
        assert delivered.status_code == 200, delivered.text
        assert delivered.json()["delivered_at"] is not None

        listed = await client.get("/api/v1/deliveries", headers=headers)
        assert listed.status_code == 200, listed.text
        assert any(row["id"] == order_id for row in listed.json())
        filtered = await client.get("/api/v1/deliveries?status=delivered", headers=headers)
        assert all(row["delivery_status"] == "delivered" for row in filtered.json())

        takeaway = await client.post("/api/v1/orders", headers=headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash", "order_type": "takeaway"})
        rejected = await client.patch(f"/api/v1/orders/{takeaway.json()['id']}/delivery", headers=headers, json={"status": "assigned"})
        assert rejected.status_code == 400, rejected.text

        invalid = await client.patch(f"/api/v1/orders/{order_id}/delivery", headers=headers, json={"status": "nonsense"})
        assert invalid.status_code == 422, invalid.text
