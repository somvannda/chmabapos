"""Admin global search and CSV exports."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def create_free_workspace(client: AsyncClient, email: str, company_name: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Search Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": company_name, "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
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
async def test_search_and_export_require_platform_admin() -> None:
    token = uuid.uuid4().hex[:10]
    email = f"admin-search-{token}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email, f"SearchCo {token}")
            company_id = workspace["company"]["id"]
            assert (await client.get("/api/v1/admin/search", headers=headers, params={"q": token})).status_code == 403
            assert (await client.get("/api/v1/admin/export/users.csv", headers=headers)).status_code == 403
            assert (await client.get("/api/v1/admin/export/companies.csv", headers=headers)).status_code == 403
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_search_finds_users_companies_and_stores() -> None:
    token = uuid.uuid4().hex[:10]
    email = f"admin-search-{token}@example.com"
    company_name = f"SearchCo {token}"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email, company_name)
            company_id = workspace["company"]["id"]
        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)

            response = await client.get("/api/v1/admin/search", headers=admin_headers, params={"q": token})
            assert response.status_code == 200
            data = response.json()
            assert data["query"] == token
            assert any(user["email"] == email for user in data["users"])
            assert any(company["name"] == company_name for company in data["companies"])
            assert any(store["company_name"] == company_name for store in data["stores"])

            short = await client.get("/api/v1/admin/search", headers=admin_headers, params={"q": "a"})
            assert short.status_code == 200
            body = short.json()
            assert body["users"] == [] and body["companies"] == [] and body["stores"] == []
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_csv_exports_include_our_records() -> None:
    token = uuid.uuid4().hex[:10]
    email = f"admin-search-{token}@example.com"
    company_name = f"SearchCo {token}"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email, company_name)
            company_id = workspace["company"]["id"]
        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)

            users_csv = await client.get("/api/v1/admin/export/users.csv", headers=admin_headers)
            assert users_csv.status_code == 200
            assert "text/csv" in users_csv.headers.get("content-type", "")
            assert "email" in users_csv.text.splitlines()[0]
            assert email in users_csv.text

            companies_csv = await client.get("/api/v1/admin/export/companies.csv", headers=admin_headers)
            assert companies_csv.status_code == 200
            assert "text/csv" in companies_csv.headers.get("content-type", "")
            assert "plan_code" in companies_csv.text.splitlines()[0]
            assert company_name in companies_csv.text
    finally:
        await cleanup(email, company_id)
