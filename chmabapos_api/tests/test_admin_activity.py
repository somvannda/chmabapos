"""Unified platform activity feed and business KPIs for the control room.

The feed merges cross-tenant ``PlatformActivity`` events with platform-admin
``AuditLog`` actuations, so the admin no longer only sees its own actions.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Activity Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Activity Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
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
async def test_activity_and_overview_require_platform_admin() -> None:
    email = f"admin-act-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            assert (await client.get("/api/v1/admin/activity", headers=headers)).status_code == 403
            assert (await client.get("/api/v1/admin/overview", headers=headers)).status_code == 403
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_activity_feed_merges_platform_and_admin_events() -> None:
    email = f"admin-act-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)

            # A company status change is an admin actuation -> audit_logs.
            update = await client.patch(f"/api/v1/admin/companies/{company_id}", headers=admin_headers, json={"is_active": True})
            assert update.status_code == 200

            # Platform events for this user (signup, logins) are found by email,
            # which keeps the assertion safe on a shared database.
            platform_response = await client.get("/api/v1/admin/activity", headers=admin_headers, params={"source": "platform", "search": email, "limit": 200})
            assert platform_response.status_code == 200
            platform = platform_response.json()
            assert platform, "expected platform events for the workspace"
            assert all(row["source"] == "platform" for row in platform)
            signup = next((row for row in platform if row["event_type"] == "user.registered"), None)
            assert signup is not None
            assert signup["title"] == "New signup"
            assert signup["actor_email"] == email

            # Admin actuations come back as the second source.
            admin_response = await client.get("/api/v1/admin/activity", headers=admin_headers, params={"source": "admin", "search": email, "limit": 200})
            assert admin_response.status_code == 200
            admin_rows = admin_response.json()
            assert admin_rows, "expected admin actuations"
            assert all(row["source"] == "admin" for row in admin_rows)
            changed = next((row for row in admin_rows if row["event_type"] == "admin.company_status_changed"), None)
            assert changed is not None
            assert changed["title"] == "Company status changed"
            assert changed["actor_email"] == email

            # Filtering to a single source never leaks the other.
            only_admin = (await client.get("/api/v1/admin/activity", headers=admin_headers, params={"source": "admin", "limit": 50})).json()
            assert all(row["source"] == "admin" for row in only_admin)
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_overview_includes_business_kpis() -> None:
    email = f"admin-act-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)
            response = await client.get("/api/v1/admin/overview", headers=admin_headers)
            assert response.status_code == 200
            data = response.json()
            for field in (
                "users", "active_users", "companies", "active_companies", "stores", "active_stores",
                "paid_subscriptions", "pending_subscriptions", "new_users_7d", "new_users_30d",
                "new_companies_30d", "active_users_30d", "orders_total", "orders_30d", "gmv_30d",
                "gmv_currency", "platform_revenue_total", "platform_revenue_30d", "mrr",
            ):
                assert field in data, field
            assert isinstance(data["new_users_30d"], int)
            assert isinstance(data["orders_30d"], int)
            assert data["gmv_currency"]
    finally:
        await cleanup(email, company_id)
