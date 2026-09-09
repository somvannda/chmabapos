from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.billing import load_entitlement
from app.db import SessionLocal
from app.main import app
from app.models import Subscription
from app.services.recurring_paddle import sync_subscription_state


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Recurring Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Recurring Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json(), headers


async def login_headers(client: AsyncClient, email: str) -> dict:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def prepaid_subscription(company_id: str, plan_code: str, ends_at: datetime) -> None:
    async with SessionLocal() as db:
        subs = list((await db.execute(text("SELECT id FROM subscriptions WHERE company_id = :company_id"), {"company_id": company_id})).mappings())
        for sub in subs:
            await db.execute(text("UPDATE subscriptions SET status = 'canceled' WHERE id = :sub_id"), {"sub_id": sub["id"]})
        db.add(
            Subscription(
                company_id=uuid.UUID(company_id),
                plan_code=plan_code,
                billing_cycle="monthly",
                status="active",
                starts_at=now_utc() - timedelta(days=10),
                ends_at=ends_at,
            )
        )
        await db.commit()


async def cleanup(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM recurring_subscriptions WHERE company_id = :company_id",
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
async def test_recurring_activation_takes_over_prepaid_and_governs() -> None:
    email = f"recur-active-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        await prepaid_subscription(company_id, "pro", now_utc() + timedelta(days=20))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await login_headers(client, email)
            activate = await client.post(
                "/api/v1/billing/recurring/mock-activate", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly"}
            )
            assert activate.status_code == 201, activate.text
            assert activate.json()["status"] == "active"
            assert activate.json()["plan_code"] == "starter"
        async with SessionLocal() as db:
            ent = await load_entitlement(db, uuid.UUID(company_id))
            assert ent.recurring is not None
            assert ent.plan.code == "starter"
            assert ent.subscription is None
            prepaids = list(
                (
                    await db.execute(text("SELECT status FROM subscriptions WHERE company_id = :cid AND plan_code != 'free'"), {"cid": company_id})
                ).mappings()
            )
            assert all(row["status"] == "canceled" for row in prepaids)
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_recurring_cancel_falls_back_to_free() -> None:
    email = f"recur-cancel-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            activate = await client.post(
                "/api/v1/billing/recurring/mock-activate", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"}
            )
            assert activate.status_code == 201
            subscription_id = activate.json()["paddle_subscription_id"]
        async with SessionLocal() as db:
            before = await load_entitlement(db, uuid.UUID(company_id))
            assert before.plan.code == "pro"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            event = {
                "event_id": f"evt-{uuid.uuid4().hex}",
                "event_type": "subscription.canceled",
                "occurred_at": now_utc().isoformat(),
                "data": {"id": subscription_id, "customer_id": "mock_ctm", "status": "canceled"},
            }
            response = await client.post("/api/v1/webhooks/paddle", json=event)
            assert response.status_code == 204, response.text
        async with SessionLocal() as db:
            ent = await load_entitlement(db, uuid.UUID(company_id))
            assert ent.recurring is None
            assert ent.plan.code == "free"
            free_rows = list(
                (await db.execute(text("SELECT id FROM subscriptions WHERE company_id = :cid AND plan_code = 'free' AND status = 'active'"), {"cid": company_id})).mappings()
            )
            assert free_rows
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_recurring_bridges_new_customer_by_email() -> None:
    email = f"recur-bridge-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        async with SessionLocal() as db:
            ok = await sync_subscription_state(
                db,
                paddle_subscription_id=f"sub_{uuid.uuid4().hex}",
                customer_id=f"ctm_{uuid.uuid4().hex}",
                customer_email=email,
                price_id=None,
                plan_code="starter",
                billing_cycle="monthly",
                status="active",
                starts_at=now_utc(),
                ends_at=now_utc() + timedelta(days=30),
            )
            assert ok is True
            ent = await load_entitlement(db, uuid.UUID(company_id))
            assert ent.recurring is not None
            assert ent.plan.code == "starter"
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_recurring_blocks_prepaid_checkout_and_schedule() -> None:
    email = f"recur-block-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            await client.post("/api/v1/billing/recurring/mock-activate", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
            prepaid = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly"})
            assert prepaid.status_code == 409
            scheduled = await client.put("/api/v1/billing/schedule", headers=headers, json={"plan_code": "starter", "keep_store_ids": [], "keep_member_ids": []})
            assert scheduled.status_code == 400
            recurring = await client.get("/api/v1/billing/recurring", headers=headers)
            assert recurring.status_code == 200
            assert recurring.json()["plan_code"] == "pro"
            subscription = await client.get("/api/v1/billing/subscription", headers=headers)
            assert subscription.status_code == 200
            assert subscription.json()["plan_code"] == "pro"
    finally:
        await cleanup(email, company_id)
