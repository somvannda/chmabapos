from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.v1 import require_plan_feature
from app.billing import load_entitlement
from app.db import SessionLocal
from app.main import app
from app.models import Subscription


class _FakeCutLuy:
    async def create_payment(self, amount, reference, metadata):
        return {
            "id": f"mock_{uuid.uuid4().hex}",
            "reference_id": reference,
            "currency": "USD",
            "status": "pending",
            "qr_string": "chmaba-plan",
            "checkout_url": None,
            "metadata": metadata,
        }


async def _fake_cutluy_factory(db):
    return _FakeCutLuy()


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Billing Test Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Billing Entitlement Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json(), headers


async def login_headers(client: AsyncClient, email: str) -> dict:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def replace_subscription(company_id: str, plan_code: str, ends_at: datetime) -> None:
    async with SessionLocal() as db:
        subs = list((await db.execute(text("SELECT id FROM subscriptions WHERE company_id = :company_id"), {"company_id": company_id})).mappings())
        for sub in subs:
            await db.execute(text("UPDATE subscriptions SET status = 'canceled' WHERE id = :sub_id"), {"sub_id": sub["id"]})
        db.add(Subscription(company_id=uuid.UUID(company_id), plan_code=plan_code, billing_cycle="monthly", status="active", starts_at=datetime.now(timezone.utc) - timedelta(days=30), ends_at=ends_at))
        await db.commit()


async def cleanup(email: str, company_id: str | None) -> None:
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
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_free_workspace_entitlement_and_feature_gates() -> None:
    email = f"billing-free-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        async with SessionLocal() as db:
            ent = await load_entitlement(db, company_id)
            assert ent.subscription is not None
            assert ent.plan.code == "free"
            assert ent.expired is None
            await require_plan_feature(db, company_id, "inventory_management")
            with pytest.raises(HTTPException) as exc_info:
                await require_plan_feature(db, company_id, "purchasing")
            assert "Free plan" in exc_info.value.detail
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_expired_paid_plan_falls_back_to_free_and_blocks_paid_features() -> None:
    email = f"billing-expired-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        async with SessionLocal() as db:
            await replace_subscription(company_id, "pro", datetime.now(timezone.utc) - timedelta(days=1))
            ent = await load_entitlement(db, company_id)
            assert ent.subscription is None
            assert ent.plan.code == "free"
            assert ent.expired is not None
            assert ent.expired.plan_code == "pro"
            with pytest.raises(HTTPException) as exc_info:
                await require_plan_feature(db, company_id, "purchasing")
            assert "expired" in exc_info.value.detail
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_in_force_paid_plan_grants_paid_features() -> None:
    email = f"billing-active-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        async with SessionLocal() as db:
            await replace_subscription(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=29))
            ent = await load_entitlement(db, company_id)
            assert ent.subscription is not None
            assert ent.plan.code == "pro"
            assert ent.expired is None
            await require_plan_feature(db, company_id, "purchasing")
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_same_plan_renewal_allowed_after_expiry(monkeypatch) -> None:
    email = f"billing-renew-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        await replace_subscription(company_id, "pro", datetime.now(timezone.utc) - timedelta(days=1))
        monkeypatch.setattr("app.api.v1.cutluy_client_for", _fake_cutluy_factory)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await login_headers(client, email)
            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
            assert checkout.status_code == 201
            assert checkout.json()["subscription"]["status"] == "pending"
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_same_plan_checkout_stacks_while_in_force(monkeypatch) -> None:
    email = f"billing-conflict-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        await replace_subscription(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=29))
        monkeypatch.setattr("app.api.v1.cutluy_client_for", _fake_cutluy_factory)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await login_headers(client, email)
            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
            assert checkout.status_code == 201
            assert checkout.json()["subscription"]["status"] == "pending"
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_card_checkout_via_paddle_mock_activates_plan() -> None:
    email = f"billing-card-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "annual", "payment_method": "card"})
            assert checkout.status_code == 201
            body = checkout.json()
            assert body["subscription"]["status"] == "pending"
            assert body["payment"]["provider"] == "paddle"
            assert body["payment"]["status"] == "pending"
            assert body["payment"]["checkout_url"].startswith("http://localhost:8000/api/v1/mock/paddle/")
            external_id = body["payment"]["external_id"]
            assert external_id.startswith("mock_paddle_")
            complete = await client.post(f"/api/v1/mock/paddle/{external_id}/complete")
            assert complete.status_code == 204
        async with SessionLocal() as db:
            ent = await load_entitlement(db, company_id)
            assert ent.subscription is not None
            assert ent.subscription.plan_code == "starter"
            assert ent.plan.code == "starter"
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_khqr_checkout_stays_on_cutluy_provider(monkeypatch) -> None:
    email = f"billing-khqr-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            monkeypatch.setattr("app.api.v1.cutluy_client_for", _fake_cutluy_factory)
            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly"})
            assert checkout.status_code == 201
            body = checkout.json()
            assert body["payment"]["provider"] == "cutluy"
    finally:
        await cleanup(email, company_id)
