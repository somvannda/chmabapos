"""Admin revenue and billing analytics for the platform's own plan fees."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Billing Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Billing Analytics Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
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
async def test_billing_analytics_requires_platform_admin() -> None:
    email = f"admin-ba-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            denied = await client.get("/api/v1/admin/billing-analytics", headers=headers)
            assert denied.status_code == 403
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_billing_analytics_reports_revenue_and_payments() -> None:
    email = f"admin-ba-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly"})
            assert checkout.status_code == 201
        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)
            response = await client.get("/api/v1/admin/billing-analytics", headers=admin_headers)
            assert response.status_code == 200
            data = response.json()
            for field in (
                "mrr", "arr", "revenue_total", "revenue_30d", "refunds_total", "payments_total",
                "payments_paid", "payments_pending", "payment_success_rate",
                "active_subscriptions", "pending_subscriptions", "plan_mix", "cycle_mix", "status_breakdown",
            ):
                assert field in data, field
            assert float(data["arr"]) == round(float(data["mrr"]) * 12, 2)
            rate = data["payment_success_rate"]
            assert rate is None or 0 <= float(rate) <= 1
            assert data["payments_paid"] <= data["payments_total"]
            assert isinstance(data["plan_mix"], list)
            assert isinstance(data["cycle_mix"], list)
            assert isinstance(data["status_breakdown"], list)
            # Our checkout is pending, so the breakdown must include a pending bucket.
            pending = next((row for row in data["status_breakdown"] if row["status"] == "pending"), None)
            assert pending is not None
            assert pending["payments"] >= 1
            assert data["payments_pending"] >= 1
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_billing_analytics_ignores_future_stacked_subscriptions() -> None:
    """A prepaid renewal (a future-dated ``active`` row) must not inflate MRR."""
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    from app.models import Subscription

    email = f"admin-ba-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            await promote_to_admin(email)
            admin = await login_headers(client, email)

            before = (await client.get("/api/v1/admin/billing-analytics", headers=admin)).json()

            now = datetime.now(timezone.utc)
            async with SessionLocal() as db:
                # One in-force paid subscription plus a future-dated prepaid renewal.
                db.add(Subscription(company_id=uuid.UUID(company_id), plan_code="starter", billing_cycle="monthly", status="active", starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=29), created_at=now))
                db.add(Subscription(company_id=uuid.UUID(company_id), plan_code="starter", billing_cycle="monthly", status="active", starts_at=now + timedelta(days=29), ends_at=now + timedelta(days=59), created_at=now))
                await db.commit()

            after = (await client.get("/api/v1/admin/billing-analytics", headers=admin)).json()
            # Only the in-force subscription counts; the future-stacked one is ignored.
            assert after["active_subscriptions"] - before["active_subscriptions"] == 1
            assert Decimal(str(after["mrr"])) - Decimal(str(before["mrr"])) > 0
    finally:
        await cleanup(email, company_id)
