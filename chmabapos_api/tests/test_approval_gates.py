from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def _owner_workspace(client: AsyncClient) -> tuple[dict[str, str], str, str]:
    email = f"approval-gates-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Gates Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Approval Gates Co", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    workspace = setup.json()
    return {**headers, "X-Store-ID": workspace["store"]["id"]}, workspace["company"]["id"], workspace["store"]["id"]


async def _add_manager(client: AsyncClient, company_id: str, store_id: str) -> dict[str, str]:
    email = f"approval-gates-mgr-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Gates Manager", "password": "strong-password"})
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


def _policy(action: str, mode: str, threshold: str, approvers: list[str]) -> dict:
    return {"enabled": True, "maker_checker": True, "expiry_minutes": 60, "notify_in_app": True, "notify_telegram": False, "rules": {action: {"mode": mode, "threshold": threshold, "approvers": approvers}}}


async def _on_hand(client: AsyncClient, headers: dict[str, str], product_id: str) -> int:
    inventory = await client.get("/api/v1/inventory", headers=headers)
    assert inventory.status_code == 200, inventory.text
    row = next(entry for entry in inventory.json() if entry["product_id"] == product_id)
    return row["on_hand"]


@pytest.mark.asyncio
async def test_stock_write_off_below_threshold_runs() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _company, _store = await _owner_workspace(client)
        await client.put("/api/v1/approval-policy", headers=headers, json=_policy("stock_write_off", "approval", "5", ["owner"]))
        product = await client.post("/api/v1/products", headers=headers, json={"name": "Small Adjust", "sku": f"SA-{uuid.uuid4().hex[:8]}", "price": "10.00", "opening_stock": 20})
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]

        adjusted = await client.patch(f"/api/v1/inventory/{product_id}", headers=headers, json={"quantity": 18, "reason": "stock count"})
        assert adjusted.status_code == 200, adjusted.text
        assert await _on_hand(client, headers, product_id) == 18


@pytest.mark.asyncio
async def test_stock_write_off_above_threshold_needs_approval_and_then_executes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, company_id, store_id = await _owner_workspace(client)
        manager = await _add_manager(client, company_id, store_id)
        await client.put("/api/v1/approval-policy", headers=headers, json=_policy("stock_write_off", "approval", "5", ["owner"]))
        product = await client.post("/api/v1/products", headers=headers, json={"name": "Write-off Widget", "sku": f"WO-{uuid.uuid4().hex[:8]}", "price": "10.00", "opening_stock": 20})
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]

        requested = await client.patch(f"/api/v1/inventory/{product_id}", headers=manager, json={"quantity": 1, "reason": "damaged"})
        assert requested.status_code == 202, requested.text
        assert requested.json()["status"] == "pending_approval"
        request_id = requested.json()["approval_request"]["id"]

        # Nothing is applied until an approver decides.
        assert await _on_hand(client, headers, product_id) == 20

        approved = await client.post(f"/api/v1/approvals/{request_id}/approve", headers=headers, json={"reason": "ok"})
        assert approved.status_code == 200, approved.text
        assert await _on_hand(client, headers, product_id) == 1


@pytest.mark.asyncio
async def test_loyalty_adjust_above_threshold_needs_approval_and_then_executes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, company_id, store_id = await _owner_workspace(client)
        manager = await _add_manager(client, company_id, store_id)
        await client.put("/api/v1/approval-policy", headers=headers, json=_policy("loyalty_adjust", "approval", "5", ["owner"]))
        customer = await client.post("/api/v1/customers", headers=headers, json={"name": "Points Person"})
        assert customer.status_code == 201, customer.text
        customer_id = customer.json()["id"]

        requested = await client.patch(f"/api/v1/customers/{customer_id}/points", headers=manager, json={"delta": 10})
        assert requested.status_code == 202, requested.text
        assert requested.json()["status"] == "pending_approval"
        request_id = requested.json()["approval_request"]["id"]

        approved = await client.post(f"/api/v1/approvals/{request_id}/approve", headers=headers, json={})
        assert approved.status_code == 200, approved.text
        assert approved.json()["points"] == 10

        detail = await client.get(f"/api/v1/customers/{customer_id}", headers=headers)
        assert float(detail.json()["customer"]["points"]) == 10


@pytest.mark.asyncio
async def test_loyalty_adjust_below_threshold_runs() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _company, _store = await _owner_workspace(client)
        await client.put("/api/v1/approval-policy", headers=headers, json=_policy("loyalty_adjust", "approval", "5", ["owner"]))
        customer = await client.post("/api/v1/customers", headers=headers, json={"name": "Small Points"})
        customer_id = customer.json()["id"]
        adjusted = await client.patch(f"/api/v1/customers/{customer_id}/points", headers=headers, json={"delta": 3})
        assert adjusted.status_code == 200, adjusted.text
        assert adjusted.json()["points"] == 3
