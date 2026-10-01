"""Admin 360-degree view of a single account: roles, sessions and activity."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict, str]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Detail Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "User Detail Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json(), headers, me.json()["id"]


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
async def test_user_detail_requires_platform_admin() -> None:
    email = f"admin-user-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers, user_id = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            denied = await client.get(f"/api/v1/admin/users/{user_id}", headers=headers)
            assert denied.status_code == 403
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_user_detail_returns_memberships_sessions_and_activity() -> None:
    email = f"admin-user-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _, user_id = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)

            response = await client.get(f"/api/v1/admin/users/{user_id}", headers=admin_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == user_id
            assert data["email"] == email
            assert data["company_count"] == 1
            assert any(m["company_name"] == "User Detail Store" and m["role"] == "owner" for m in data["memberships"])
            assert len(data["sessions"]) >= 1
            assert data["last_login"]
            assert any(row["event_type"] == "user.registered" for row in data["recent_activity"])
            assert all(row["source"] == "platform" for row in data["recent_activity"])

            missing = await client.get(f"/api/v1/admin/users/{uuid.uuid4()}", headers=admin_headers)
            assert missing.status_code == 404
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_user_list_includes_last_login() -> None:
    email = f"admin-user-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)
            rows = (await client.get("/api/v1/admin/users", headers=admin_headers, params={"search": email})).json()
            row = next((item for item in rows if item["email"] == email), None)
            assert row is not None
            assert row["last_login"]
    finally:
        await cleanup(email, company_id)
