"""Admin visibility over plan-fee payments (item 6)."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Admin View Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Admin View Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json(), headers


async def cleanup(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM subscription_capacity_actions WHERE company_id = :company_id",
                "DELETE FROM billing_refunds WHERE company_id = :company_id",
                "DELETE FROM billing_receipts WHERE company_id = :company_id",
                "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                "DELETE FROM subscriptions WHERE company_id = :company_id",
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


async def make_billing_payment(client: AsyncClient, headers: dict, plan_code: str = "starter") -> dict:
    response = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": plan_code, "billing_cycle": "monthly"})
    assert response.status_code == 201
    return response.json()["payment"]


async def promote_to_admin(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": email})
        await db.commit()


async def login_headers(client: AsyncClient, email: str) -> dict:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_billing_payments_requires_platform_admin() -> None:
    email = f"admin-bp-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            denied = await client.get("/api/v1/admin/billing-payments", headers=headers)
            assert denied.status_code == 403
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_admin_lists_and_filters_billing_payments() -> None:
    email = f"admin-bp-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            payment = await make_billing_payment(client, headers)
        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)

            listed = await client.get("/api/v1/admin/billing-payments", headers=admin_headers)
            assert listed.status_code == 200
            row = next((item for item in listed.json() if item["id"] == payment["id"]), None)
            assert row is not None
            assert row["company_id"] == company_id
            assert row["company_name"] == "Admin View Store"
            assert row["plan_code"] == "starter"
            assert row["status"] == "pending"
            assert row["provider"] == "chamabapay"
            # Never leak secret material.
            assert "api_key" not in row and "api_key_preview" not in row
            assert "webhook_secret" not in row and "webhook_secret_preview" not in row

            by_company = await client.get(f"/api/v1/admin/billing-payments?company_id={company_id}", headers=admin_headers)
            assert by_company.status_code == 200
            assert by_company.json() and all(item["company_id"] == company_id for item in by_company.json())

            by_status = await client.get("/api/v1/admin/billing-payments?status=pending", headers=admin_headers)
            assert by_status.status_code == 200
            assert all(item["status"] == "pending" for item in by_status.json())
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_admin_settings_surface_resolved_platform_store() -> None:
    email = f"admin-bp-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)
            settings = await client.get("/api/v1/admin/chamabapay-settings", headers=admin_headers)
            assert settings.status_code == 200
            body = settings.json()
            assert "resolved_platform_store_id" in body
            assert body["resolved_platform_store_id"]
            # Only masked previews are exposed, never the raw secret.
            assert "chamabapay_api_key" not in body
            assert "chamabapay_webhook_secret" not in body
    finally:
        await cleanup(email, company_id)
