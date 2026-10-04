from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def _owner_workspace(client: AsyncClient) -> tuple[dict[str, str], str, str]:
    email = f"cancel-paid-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Cancel Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Cancel Paid Co", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    workspace = setup.json()
    return {**headers, "X-Store-ID": workspace["store"]["id"]}, workspace["company"]["id"], workspace["store"]["id"]


async def _add_manager(client: AsyncClient, company_id: str, store_id: str) -> dict[str, str]:
    email = f"cancel-paid-mgr-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Cancel Manager", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}", "X-Store-ID": store_id}
    async with SessionLocal() as db:
        user_id = (await db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email})).scalar_one()
        membership_id = uuid.uuid4()
        await db.execute(text("INSERT INTO memberships (id, company_id, user_id, role, status, created_at) VALUES (:id, :company_id, :user_id, 'manager', 'active', now())"), {"id": membership_id, "company_id": uuid.UUID(company_id), "user_id": user_id})
        await db.execute(text("INSERT INTO membership_stores (membership_id, store_id) VALUES (:membership_id, :store_id)"), {"membership_id": membership_id, "store_id": uuid.UUID(store_id)})
        await db.commit()
    return headers


def _policy(action: str, mode: str, approvers: list[str]) -> dict:
    return {"enabled": True, "maker_checker": True, "expiry_minutes": 60, "notify_in_app": True, "notify_telegram": False, "rules": {action: {"mode": mode, "threshold": None, "approvers": approvers}}}


async def _paid_order(client: AsyncClient, headers: dict[str, str], quantity: int = 2) -> tuple[str, str]:
    product = await client.post("/api/v1/products", headers=headers, json={"name": "Void Widget", "sku": f"VW-{uuid.uuid4().hex[:8]}", "price": "10.00", "opening_stock": 5})
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    order = await client.post("/api/v1/orders", headers=headers, json={"items": [{"product_id": product_id, "quantity": quantity}], "payment_method": "cash"})
    assert order.status_code == 201, order.text
    assert order.json()["status"] == "paid"
    return product_id, order.json()["id"]


async def _on_hand(client: AsyncClient, headers: dict[str, str], product_id: str) -> int:
    rows = (await client.get("/api/v1/inventory", headers=headers)).json()
    return next(row for row in rows if row["product_id"] == product_id)["on_hand"]


@pytest.mark.asyncio
async def test_paid_order_cancel_needs_approval_and_then_voids() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, company_id, store_id = await _owner_workspace(client)
        manager = await _add_manager(client, company_id, store_id)
        await client.put("/api/v1/approval-policy", headers=headers, json=_policy("cancel_paid_order", "approval", ["owner"]))
        product_id, order_id = await _paid_order(client, headers, 2)
        assert await _on_hand(client, headers, product_id) == 3

        requested = await client.post(f"/api/v1/orders/{order_id}/cancel", headers=manager)
        assert requested.status_code == 202, requested.text
        assert requested.json()["status"] == "pending_approval"
        request_id = requested.json()["approval_request"]["id"]
        # Nothing has changed yet.
        assert (await client.get(f"/api/v1/orders/{order_id}", headers=headers)).json()["status"] == "paid"
        assert await _on_hand(client, headers, product_id) == 3

        approved = await client.post(f"/api/v1/approvals/{request_id}/approve", headers=headers, json={})
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "cancelled"
        assert (await client.get(f"/api/v1/orders/{order_id}", headers=headers)).json()["status"] == "cancelled"
        assert await _on_hand(client, headers, product_id) == 5


@pytest.mark.asyncio
async def test_paid_order_cancel_blocked_when_policy_off() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _company, _store = await _owner_workspace(client)
        _product_id, order_id = await _paid_order(client, headers, 1)
        blocked = await client.post(f"/api/v1/orders/{order_id}/cancel", headers=headers)
        assert blocked.status_code == 409, blocked.text
