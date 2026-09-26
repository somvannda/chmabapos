"""Quota enforcement tests for the effective plan's transaction limit.

The counting window must end at the subscription's **grace deadline**, not at
``ends_at``: a plan stays in force through the 48h grace window, so sales taken
during grace still count against the same quota. Before the fix, orders created
after ``ends_at`` were excluded from the count and the limit never tripped.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.billing import Entitlement
from app.db import SessionLocal
from app.main import app
from app.models import Membership, Order, Subscription
from app.services import orders as orders_module
from app.services.orders import ensure_transaction_available


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _StubPlan:
    """Minimal stand-in for a Plan row so a test can pick a tiny limit."""

    def __init__(self, transaction_limit: int, name: str = "Starter") -> None:
        self.code = "starter"
        self.name = name
        self.transaction_limit = transaction_limit


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Quota Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Quota Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json(), headers


async def activate_subscription(company_id: str, plan_code: str, *, starts_at: datetime, ends_at: datetime | None) -> None:
    async with SessionLocal() as db:
        rows = list((await db.execute(text("SELECT id FROM subscriptions WHERE company_id = :company_id"), {"company_id": company_id})).mappings())
        for row in rows:
            await db.execute(text("UPDATE subscriptions SET status = 'canceled' WHERE id = :sub_id"), {"sub_id": row["id"]})
        db.add(Subscription(company_id=uuid.UUID(company_id), plan_code=plan_code, billing_cycle="monthly", status="active", starts_at=starts_at, ends_at=ends_at))
        await db.commit()


async def company_owner_id(company_id: str) -> str:
    async with SessionLocal() as db:
        owner_id = await db.scalar(select(Membership.user_id).where(Membership.company_id == uuid.UUID(company_id)).limit(1))
        assert owner_id is not None
        return str(owner_id)


async def insert_paid_orders(store_id: str, user_id: str, moments: list[datetime]) -> None:
    async with SessionLocal() as db:
        for index, moment in enumerate(moments):
            db.add(
                Order(
                    store_id=uuid.UUID(store_id),
                    created_by=uuid.UUID(user_id),
                    order_number=f"Q-{index}-{uuid.uuid4().hex[:8]}",
                    currency_code="USD",
                    subtotal=Decimal("1.00"),
                    total=Decimal("1.00"),
                    status="paid",
                    created_at=moment,
                    paid_at=moment,
                )
            )
        await db.commit()


async def cleanup(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM subscription_capacity_actions WHERE company_id = :company_id",
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


async def enforce_with_limit(monkeypatch: pytest.MonkeyPatch, company_id: str, limit: int) -> None:
    """Call the real quota gate with a stub plan that carries ``limit``."""
    async with SessionLocal() as db:
        cid = uuid.UUID(company_id)
        subscription = (
            await db.execute(select(Subscription).where(Subscription.company_id == cid, Subscription.status == "active"))
        ).scalars().first()
        assert subscription is not None

        async def fake_entitlement(_db, _company_id):  # type: ignore[no-untyped-def]
            return Entitlement(subscription=subscription, plan=_StubPlan(limit))

        monkeypatch.setattr(orders_module, "load_entitlement", fake_entitlement)
        await ensure_transaction_available(db, cid)


@pytest.mark.asyncio
async def test_grace_window_still_enforces_transaction_limit(monkeypatch) -> None:
    """Regression: sales taken during grace must count. Fails before the fix."""
    email = f"quota-grace-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        now = utc_now()
        # Ended yesterday: inside the grace window, so the paid plan still governs.
        await activate_subscription(company_id, "starter", starts_at=now - timedelta(days=30), ends_at=now - timedelta(days=1))
        store_id = workspace["store"]["id"]
        user_id = await company_owner_id(company_id)
        # One order inside the paid period, one after ends_at but during grace.
        await insert_paid_orders(store_id, user_id, [now - timedelta(days=2), now - timedelta(hours=1)])

        with pytest.raises(HTTPException) as exc:
            await enforce_with_limit(monkeypatch, company_id, limit=2)
        assert exc.value.status_code == 403
        assert "transaction limit" in exc.value.detail
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_pre_expiry_limit_still_blocks(monkeypatch) -> None:
    email = f"quota-pre-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        now = utc_now()
        await activate_subscription(company_id, "starter", starts_at=now - timedelta(days=30), ends_at=now + timedelta(days=10))
        store_id = workspace["store"]["id"]
        user_id = await company_owner_id(company_id)
        await insert_paid_orders(store_id, user_id, [now - timedelta(days=2), now - timedelta(hours=1)])

        with pytest.raises(HTTPException) as exc:
            await enforce_with_limit(monkeypatch, company_id, limit=2)
        assert exc.value.status_code == 403
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_below_limit_allows_sale(monkeypatch) -> None:
    email = f"quota-below-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        now = utc_now()
        await activate_subscription(company_id, "starter", starts_at=now - timedelta(days=30), ends_at=now + timedelta(days=10))
        store_id = workspace["store"]["id"]
        user_id = await company_owner_id(company_id)
        await insert_paid_orders(store_id, user_id, [now - timedelta(days=2), now - timedelta(hours=1)])

        # limit 3 > 2 counted orders: the gate must not raise.
        await enforce_with_limit(monkeypatch, company_id, limit=3)
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_orders_before_period_start_are_excluded(monkeypatch) -> None:
    email = f"quota-window-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        now = utc_now()
        # Period starts 10 days ago; one order predates it and must not count.
        await activate_subscription(company_id, "starter", starts_at=now - timedelta(days=10), ends_at=now + timedelta(days=10))
        store_id = workspace["store"]["id"]
        user_id = await company_owner_id(company_id)
        await insert_paid_orders(store_id, user_id, [now - timedelta(days=20), now - timedelta(hours=1)])

        await enforce_with_limit(monkeypatch, company_id, limit=2)
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_free_plan_window_is_open_ended(monkeypatch) -> None:
    email = f"quota-free-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        now = utc_now()
        # Free plan: no ends_at, so the window has no upper bound.
        await activate_subscription(company_id, "free", starts_at=now - timedelta(days=30), ends_at=None)
        store_id = workspace["store"]["id"]
        user_id = await company_owner_id(company_id)
        await insert_paid_orders(store_id, user_id, [now - timedelta(days=2), now - timedelta(hours=1)])

        with pytest.raises(HTTPException) as exc:
            await enforce_with_limit(monkeypatch, company_id, limit=2)
        assert exc.value.status_code == 403
    finally:
        await cleanup(email, company_id)
