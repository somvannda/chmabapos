from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def _owner_workspace(client: AsyncClient) -> tuple[dict[str, str], str, str]:
    email = f"approval-price-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Price Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Approval Price Co", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    workspace = setup.json()
    return {**headers, "X-Store-ID": workspace["store"]["id"]}, workspace["company"]["id"], workspace["store"]["id"]


async def _add_manager(client: AsyncClient, company_id: str, store_id: str) -> dict[str, str]:
    email = f"approval-price-mgr-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Price Manager", "password": "strong-password"})
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


def _policy(action: str, mode: str, approvers: list[str], threshold: str | None = None) -> dict:
    return {"enabled": True, "maker_checker": True, "expiry_minutes": 60, "notify_in_app": True, "notify_telegram": False, "rules": {action: {"mode": mode, "threshold": threshold, "approvers": approvers}}}


async def _create_product(client: AsyncClient, headers: dict[str, str], price: str = "10.00") -> str:
    product = await client.post("/api/v1/products", headers=headers, json={"name": "Priced Widget", "sku": f"PR-{uuid.uuid4().hex[:8]}", "price": price, "opening_stock": 5})
    assert product.status_code == 201, product.text
    return product.json()["id"]


async def _price(client: AsyncClient, headers: dict[str, str], product_id: str) -> str:
    rows = (await client.get("/api/v1/products", headers=headers)).json()
    return next(row for row in rows if row["id"] == product_id)["price"]


@pytest.mark.asyncio
async def test_price_edit_needs_approval_and_then_executes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, company_id, store_id = await _owner_workspace(client)
        manager = await _add_manager(client, company_id, store_id)
        await client.put("/api/v1/approval-policy", headers=headers, json=_policy("price_cost_edit", "approval", ["owner"]))
        product_id = await _create_product(client, headers, "10.00")

        requested = await client.patch(f"/api/v1/products/{product_id}", headers=manager, json={"price": "12.00"})
        assert requested.status_code == 202, requested.text
        assert requested.json()["status"] == "pending_approval"
        request_id = requested.json()["approval_request"]["id"]
        assert await _price(client, headers, product_id) == "10.00"

        approved = await client.post(f"/api/v1/approvals/{request_id}/approve", headers=headers, json={})
        assert approved.status_code == 200, approved.text
        assert approved.json()["price"] == "12.00"
        assert await _price(client, headers, product_id) == "12.00"


@pytest.mark.asyncio
async def test_price_edit_review_applies_immediately() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _company, _store = await _owner_workspace(client)
        await client.put("/api/v1/approval-policy", headers=headers, json=_policy("price_cost_edit", "review", ["owner"]))
        product_id = await _create_product(client, headers, "10.00")
        edited = await client.patch(f"/api/v1/products/{product_id}", headers=headers, json={"price": "15.00"})
        assert edited.status_code == 200, edited.text
        assert await _price(client, headers, product_id) == "15.00"


@pytest.mark.asyncio
async def test_rename_is_not_gated() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, company_id, store_id = await _owner_workspace(client)
        manager = await _add_manager(client, company_id, store_id)
        await client.put("/api/v1/approval-policy", headers=headers, json=_policy("price_cost_edit", "approval", ["owner"]))
        product_id = await _create_product(client, headers, "10.00")
        renamed = await client.patch(f"/api/v1/products/{product_id}", headers=manager, json={"name": "Renamed Widget"})
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["name"] == "Renamed Widget"
        assert renamed.json()["price"] == "10.00"
