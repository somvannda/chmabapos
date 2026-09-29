from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def _owner_workspace(client: AsyncClient) -> tuple[dict[str, str], str, str]:
    email = f"approval-refund-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Refund Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Approval Refund Co", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    workspace = setup.json()
    return {**headers, "X-Store-ID": workspace["store"]["id"]}, workspace["company"]["id"], workspace["store"]["id"]


async def _paid_order(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    product = await client.post("/api/v1/products", headers=headers, json={"name": "Refund Laptop", "sku": f"RF-{uuid.uuid4().hex[:8]}", "price": "100.00", "opening_stock": 10})
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    order = await client.post("/api/v1/orders", headers=headers, json={"items": [{"product_id": product_id, "quantity": 3}], "payment_method": "cash"})
    assert order.status_code == 201, order.text
    assert order.json()["status"] == "paid"
    return product_id, order.json()["id"]


async def _add_manager(client: AsyncClient, company_id: str, store_id: str) -> dict[str, str]:
    email = f"approval-manager-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Refund Manager", "password": "strong-password"})
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


def _policy(mode: str, threshold: str, approvers: list[str]) -> dict:
    return {"enabled": True, "maker_checker": True, "expiry_minutes": 60, "notify_in_app": True, "notify_telegram": False, "rules": {"refund": {"mode": mode, "threshold": threshold, "approvers": approvers}}}


@pytest.mark.asyncio
async def test_refund_below_threshold_just_runs() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _company, _store = await _owner_workspace(client)
        await client.put("/api/v1/approval-policy", headers=headers, json=_policy("approval", "1000", ["owner"]))
        product_id, order_id = await _paid_order(client, headers)
        refund = await client.post(f"/api/v1/orders/{order_id}/refund", headers=headers, json={"items": [{"product_id": product_id, "quantity": 1}], "method": "cash"})
        assert refund.status_code == 201, refund.text
        assert refund.json()["total"] == "110.00"


@pytest.mark.asyncio
async def test_refund_above_threshold_needs_approval_and_then_executes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, company_id, store_id = await _owner_workspace(client)
        manager = await _add_manager(client, company_id, store_id)
        await client.put("/api/v1/approval-policy", headers=headers, json=_policy("approval", "5", ["owner"]))
        product_id, order_id = await _paid_order(client, headers)

        requested = await client.post(f"/api/v1/orders/{order_id}/refund", headers=manager, json={"items": [{"product_id": product_id, "quantity": 1}], "method": "cash"})
        assert requested.status_code == 202, requested.text
        assert requested.json()["status"] == "pending_approval"
        request_id = requested.json()["approval_request"]["id"]

        pending = await client.get("/api/v1/approvals?status=pending", headers=headers)
        assert pending.status_code == 200, pending.text
        assert any(row["id"] == request_id and row["action"] == "refund" for row in pending.json())

        approved = await client.post(f"/api/v1/approvals/{request_id}/approve", headers=headers, json={"reason": "customer was right"})
        assert approved.status_code == 200, approved.text
        assert approved.json()["total"] == "110.00"

        order = await client.get(f"/api/v1/orders/{order_id}", headers=headers)
        assert order.json()["status"] == "paid"  # partial refund leaves it paid


@pytest.mark.asyncio
async def test_a_manager_cannot_approve_their_own_request() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, company_id, store_id = await _owner_workspace(client)
        manager = await _add_manager(client, company_id, store_id)
        # Both roles may approve, so maker-checker is what stops the requester.
        await client.put("/api/v1/approval-policy", headers=headers, json=_policy("approval", "5", ["owner", "manager"]))
        product_id, order_id = await _paid_order(client, headers)

        requested = await client.post(f"/api/v1/orders/{order_id}/refund", headers=manager, json={"items": [{"product_id": product_id, "quantity": 1}], "method": "cash"})
        assert requested.status_code == 202, requested.text
        request_id = requested.json()["approval_request"]["id"]

        blocked = await client.post(f"/api/v1/approvals/{request_id}/approve", headers=manager, json={})
        assert blocked.status_code == 403, blocked.text

        rejected = await client.post(f"/api/v1/approvals/{request_id}/reject", headers=headers, json={"reason": "not today"})
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "rejected"
