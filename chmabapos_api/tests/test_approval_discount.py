from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _owner(client: AsyncClient) -> dict[str, str]:
    email = f"discount-review-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Discount Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Discount Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    return {**headers, "X-Store-ID": setup.json()["store"]["id"]}


async def _discount_reviews(client: AsyncClient, headers: dict[str, str]) -> list[dict]:
    response = await client.get("/api/v1/audit-logs", headers=headers)
    assert response.status_code == 200, response.text
    return [row for row in response.json() if row["action"] == "discount_reviewed"]


@pytest.mark.asyncio
async def test_a_large_discount_is_flagged_and_a_small_one_is_not() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _owner(client)
        product = await client.post("/api/v1/products", headers=headers, json={"name": "Discount Laptop", "sku": f"DL-{uuid.uuid4().hex[:8]}", "price": "100.00", "opening_stock": 5})
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]

        policy = await client.put(
            "/api/v1/approval-policy",
            headers=headers,
            json={"enabled": True, "maker_checker": True, "expiry_minutes": 60, "notify_in_app": True, "notify_telegram": False, "rules": {"discount": {"mode": "review", "threshold": "10", "approvers": ["owner"]}}},
        )
        assert policy.status_code == 200, policy.text

        small = await client.post("/api/v1/orders", headers=headers, json={"items": [{"product_id": product_id, "quantity": 1}], "discount": "5.00", "payment_method": "cash"})
        assert small.status_code == 201, small.text
        assert await _discount_reviews(client, headers) == []

        large = await client.post("/api/v1/orders", headers=headers, json={"items": [{"product_id": product_id, "quantity": 1}], "discount": "30.00", "payment_method": "cash"})
        assert large.status_code == 201, large.text
        reviews = await _discount_reviews(client, headers)
        assert len(reviews) == 1
        assert reviews[0]["details"]["percent"] == "30.00"
        assert reviews[0]["details"]["order_number"] == large.json()["order_number"]


@pytest.mark.asyncio
async def test_discounts_are_not_flagged_when_the_policy_is_off() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _owner(client)
        product = await client.post("/api/v1/products", headers=headers, json={"name": "No Policy Laptop", "sku": f"NP-{uuid.uuid4().hex[:8]}", "price": "100.00", "opening_stock": 5})
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]

        order = await client.post("/api/v1/orders", headers=headers, json={"items": [{"product_id": product_id, "quantity": 1}], "discount": "50.00", "payment_method": "cash"})
        assert order.status_code == 201, order.text
        assert await _discount_reviews(client, headers) == []
