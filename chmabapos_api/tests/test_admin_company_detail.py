"""Admin business-health view of a single tenant."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Health Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Company Health Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json(), headers


async def promote_to_admin(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": email})
        await db.commit()


async def login_headers(client: AsyncClient, email: str) -> dict:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def cleanup(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        await db.execute(
            text("DELETE FROM platform_activities WHERE company_id = :company_id OR user_id IN (SELECT id FROM users WHERE email = :email)"),
            {"company_id": company_id, "email": email},
        )
        await db.execute(text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM subscription_capacity_actions WHERE company_id = :company_id",
                "DELETE FROM billing_refunds WHERE company_id = :company_id",
                "DELETE FROM billing_receipts WHERE company_id = :company_id",
                "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                "DELETE FROM subscriptions WHERE company_id = :company_id",
                "DELETE FROM stock_movements WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM inventory_balances WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM variant_inventory_balances WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id))",
                "DELETE FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM product_variants WHERE product_id IN (SELECT id FROM products WHERE company_id = :company_id)",
                "DELETE FROM products WHERE company_id = :company_id",
                "DELETE FROM customers WHERE company_id = :company_id",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM invitations WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM categories WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]
            for statement in statements:
                await db.execute(text(statement), parameters)
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_company_detail_requires_platform_admin() -> None:
    email = f"admin-co-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            denied = await client.get(f"/api/v1/admin/companies/{company_id}", headers=headers)
            assert denied.status_code == 403
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_company_detail_returns_business_health() -> None:
    email = f"admin-co-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            store_id = workspace["store"]["id"]
            product = await client.post(
                "/api/v1/products",
                headers={**headers, "X-Store-ID": store_id},
                json={"name": "Health Widget", "sku": f"HW-{uuid.uuid4().hex[:8]}", "price": "9.99", "opening_stock": 3},
            )
            assert product.status_code == 201
        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)

            response = await client.get(f"/api/v1/admin/companies/{company_id}", headers=admin_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == company_id
            assert data["name"] == "Company Health Store"
            assert data["default_currency_code"] == "USD"
            assert data["store_count"] >= 1
            assert data["active_store_count"] >= 1
            assert data["member_count"] >= 1
            assert data["active_member_count"] >= 1
            assert data["product_count"] >= 1
            assert data["orders_total"] == 0
            assert any(m["email"] == email and m["role"] == "owner" for m in data["members"])
            assert any(s["name"] == "Main Counter" for s in data["stores"])
            assert isinstance(data["recent_activity"], list)

            missing = await client.get(f"/api/v1/admin/companies/{uuid.uuid4()}", headers=admin_headers)
            assert missing.status_code == 404
    finally:
        await cleanup(email, company_id)
