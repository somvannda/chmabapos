from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.api.v1 import fulfill_billing_payment
from app.db import SessionLocal
from app.main import app
from app.models import Subscription

EMAIL_SUFFIX = "checkoutguard"


async def register_workspace(client: AsyncClient, email: str, plan_code: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Guard Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Guard Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": plan_code},
    )
    assert setup.status_code == 201
    return setup.json(), headers


async def activate_plan(company_id: str, plan_code: str, ends_at: datetime) -> None:
    async with SessionLocal() as db:
        rows = list((await db.execute(text("SELECT id FROM subscriptions WHERE company_id = :company_id"), {"company_id": company_id})).mappings())
        for row in rows:
            await db.execute(text("UPDATE subscriptions SET status = 'canceled' WHERE id = :sub_id"), {"sub_id": row["id"]})
        db.add(
            Subscription(
                company_id=uuid.UUID(company_id),
                plan_code=plan_code,
                billing_cycle="monthly",
                status="active",
                starts_at=datetime.now(timezone.utc) - timedelta(days=30),
                ends_at=ends_at,
            )
        )
        await db.commit()


async def cleanup(emails: list[str], company_id: str | None) -> None:
    async with SessionLocal() as db:
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
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
        for email in emails:
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_downgrade_checkout_rejected_unless_scheduled() -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]
            await activate_plan(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=30))

            downgrade = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly", "payment_method": "khqr"})
            assert downgrade.status_code == 400
            assert "downgrade" in downgrade.json()["detail"]

            scheduled = await client.put("/api/v1/billing/schedule", headers=headers, json={"plan_code": "starter"})
            assert scheduled.status_code == 200

            renewal = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly", "payment_method": "khqr"})
            assert renewal.status_code == 201
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_same_plan_renewal_checkout_still_allowed() -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]
            await activate_plan(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=30))

            renewal = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly", "payment_method": "khqr"})
            assert renewal.status_code == 201
            assert renewal.json()["subscription"]["plan_code"] == "pro"
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_cancel_pending_checkout_keeps_current_plan_and_blocks_late_payment() -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]
            await activate_plan(company_id, "starter", datetime.now(timezone.utc) + timedelta(days=30))

            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly", "payment_method": "khqr"})
            assert checkout.status_code == 201
            external_id = checkout.json()["payment"]["external_id"]

            payments = await client.get("/api/v1/billing/payments", headers=headers)
            assert payments.status_code == 200
            assert payments.json()[0]["status"] == "pending"

            cancelled = await client.delete("/api/v1/billing/checkout", headers=headers)
            assert cancelled.status_code == 200
            assert cancelled.json()["plan_code"] == "starter"
            assert cancelled.json()["status"] == "active"

            subscription = await client.get("/api/v1/billing/subscription", headers=headers)
            assert subscription.status_code == 200
            assert subscription.json()["plan_code"] == "starter"
            assert subscription.json()["status"] == "active"

            payments = await client.get("/api/v1/billing/payments", headers=headers)
            assert payments.json()[0]["status"] == "expired"

            async with SessionLocal() as db:
                activated = await fulfill_billing_payment(external_id, None, datetime.now(timezone.utc), db)
                await db.commit()
                assert activated is True
                pro_active = await db.scalar(
                    select(Subscription.id).where(Subscription.company_id == uuid.UUID(company_id), Subscription.plan_code == "pro", Subscription.status == "active")
                )
                assert pro_active is None
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_cancel_after_unpaid_onboarding_falls_back_to_free() -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "starter")
            company_id = workspace["company"]["id"]
            assert workspace["subscription"]["status"] == "pending"

            cancelled = await client.delete("/api/v1/billing/checkout", headers=headers)
            assert cancelled.status_code == 200
            assert cancelled.json()["plan_code"] == "free"
            assert cancelled.json()["status"] == "active"

            current = await client.get("/api/v1/workspaces/current", headers=headers)
            assert current.status_code == 200
            assert current.json()["subscription"]["plan_code"] == "free"
            assert current.json()["billing_payment"] is None

            async with SessionLocal() as db:
                free_active = await db.scalar(
                    select(Subscription.id).where(Subscription.company_id == uuid.UUID(company_id), Subscription.plan_code == "free", Subscription.status == "active")
                )
                assert free_active is not None
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_cancel_rejects_when_no_pending_checkout() -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]

            first = await client.delete("/api/v1/billing/checkout", headers=headers)
            assert first.status_code == 409

            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly", "payment_method": "khqr"})
            assert checkout.status_code == 201
            cancelled = await client.delete("/api/v1/billing/checkout", headers=headers)
            assert cancelled.status_code == 200
            second = await client.delete("/api/v1/billing/checkout", headers=headers)
            assert second.status_code == 409
    finally:
        await cleanup([email], company_id)
