"""A paid period keeps the terms it was sold under until renewal."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.billing import load_entitlement, plan_terms
from app.db import SessionLocal
from app.main import app
from app.models import Plan, Store, Subscription
from app.services.billing_lifecycle import reconcile_effective_capacity
from tests.test_admin_subscription_management import _cleanup as _cleanup_admin_workspace, _free_workspace
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_plan_edit_does_not_change_an_in_force_subscription() -> None:
    email: str | None = None
    company_id: str | None = None
    plan_code = f"snap-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Snapshot Store", "Main", plan="free", email_prefix="snapshot")
            email, company_id = ctx["email"], ctx["company_id"]

        async with SessionLocal() as db:
            plan = Plan(
                code=plan_code,
                name="Snapshot plan",
                monthly_price=Decimal("10.00"),
                max_stores=5,
                max_members=5,
                transaction_limit=50,
                capabilities={"inventory_management": True},
                is_active=True,
            )
            db.add(plan)
            subscription = Subscription(
                company_id=company_id,
                plan_code=plan_code,
                billing_cycle="monthly",
                status="active",
                starts_at=now - timedelta(days=1),
                ends_at=now + timedelta(days=29),
                plan_terms=plan_terms(plan),
            )
            db.add(subscription)
            await db.commit()

            # The admin lowers the live plan. The purchased period is unchanged.
            plan.max_stores = 1
            plan.max_members = 1
            plan.transaction_limit = 5
            plan.capabilities = {"inventory_management": False}
            await db.commit()

            entitlement = await load_entitlement(db, subscription.company_id)
            assert entitlement.plan.max_stores == 5
            assert entitlement.plan.max_members == 5
            assert entitlement.plan.transaction_limit == 50
            assert entitlement.plan.capabilities["inventory_management"] is True

            # A renewal re-snapshots the current terms.
            subscription.plan_terms = plan_terms(plan)
            await db.commit()
            renewed = await load_entitlement(db, subscription.company_id)
            assert renewed.plan.max_stores == 1
            assert renewed.plan.max_members == 1
            assert renewed.plan.transaction_limit == 5
            assert renewed.plan.capabilities["inventory_management"] is False
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM plans WHERE code = :code"), {"code": plan_code})
            await db.commit()


@pytest.mark.asyncio
async def test_renewal_enforces_the_purchased_limits_once() -> None:
    email: str | None = None
    company_id: str | None = None
    plan_code = f"cap-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Capacity Store", "Main", plan="free", email_prefix="capacity")
            email, company_id = ctx["email"], ctx["company_id"]

        async with SessionLocal() as db:
            plan = Plan(
                code=plan_code,
                name="Capacity plan",
                monthly_price=Decimal("10.00"),
                max_stores=1,
                max_members=5,
                transaction_limit=50,
                capabilities={},
                is_active=True,
            )
            db.add(plan)
            subscription = Subscription(
                company_id=uuid.UUID(company_id),
                plan_code=plan_code,
                billing_cycle="monthly",
                status="active",
                starts_at=now - timedelta(days=1),
                ends_at=now + timedelta(days=29),
                plan_terms=plan_terms(plan),
            )
            db.add(subscription)
            db.add(
                Store(
                    company_id=uuid.UUID(company_id),
                    name="Second",
                    slug=f"second-{uuid.uuid4().hex[:6]}",
                    currency_code="USD",
                )
            )
            await db.commit()

            stats = await reconcile_effective_capacity(db, company_ids=[uuid.UUID(company_id)])
            assert stats["companies"] == 1
            assert stats["paused_stores"] == 1

            await db.refresh(subscription)
            active = await db.scalar(
                text("SELECT count(*) FROM stores WHERE company_id = :company_id AND is_active")
                , {"company_id": company_id}
            )
            assert active == 1
            assert subscription.capacity_checked_at is not None
            assert len(subscription.paused_store_ids or []) == 1

            # A second pass is a no-op: the period has been checked.
            again = await reconcile_effective_capacity(db, company_ids=[uuid.UUID(company_id)])
            assert again["companies"] == 0
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM plans WHERE code = :code"), {"code": plan_code})
            await db.commit()


@pytest.mark.asyncio
async def test_checkout_freezes_terms_and_late_plan_edits_do_not_apply(monkeypatch) -> None:
    monkeypatch.setattr("app.api.v1.signature_is_valid", lambda *args, **kwargs: True)
    email = f"snap-checkout-{uuid.uuid4().hex[:8]}@example.com"
    company_id: str | None = None
    plan_code = f"buy-{uuid.uuid4().hex[:6]}"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace = await _free_workspace(client, email)
            company_id = workspace["company"]["id"]
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            async with SessionLocal() as db:
                db.add(
                    Plan(
                        code=plan_code,
                        name="Checkout plan",
                        monthly_price=Decimal("10.00"),
                        max_stores=5,
                        max_members=5,
                        transaction_limit=50,
                        capabilities={},
                        is_active=True,
                    )
                )
                await db.commit()

            checkout = await client.post(
                "/api/v1/billing/checkout",
                headers=headers,
                json={"plan_code": plan_code, "billing_cycle": "monthly"},
            )
            assert checkout.status_code == 201, checkout.text
            payment = checkout.json()["payment"]

            async with SessionLocal() as db:
                plan = await db.get(Plan, plan_code)
                assert plan is not None
                plan.max_stores = 1
                await db.commit()

            late = {
                "id": f"evt_{uuid.uuid4().hex}",
                "type": "payment.test",
                "created": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "payment": {
                        "id": payment["external_id"],
                        "status": "paid",
                        "amount": str(payment["amount"]),
                        "currency": "USD",
                        "reference_id": payment["reference_id"],
                    }
                },
            }
            assert (await client.post("/api/v1/webhooks/chamabapay", json=late)).status_code == 200

            async with SessionLocal() as db:
                ent = await load_entitlement(db, uuid.UUID(company_id))
                assert ent.plan.max_stores == 5

            renewal = await client.post(
                "/api/v1/billing/checkout",
                headers=headers,
                json={"plan_code": plan_code, "billing_cycle": "monthly"},
            )
            assert renewal.status_code == 201, renewal.text
            async with SessionLocal() as db:
                pending = (
                    await db.execute(
                        text("SELECT plan_terms FROM subscriptions WHERE id = :id"),
                        {"id": renewal.json()["subscription"]["id"]},
                    )
                ).scalar_one()
                assert pending["max_stores"] == 1
    finally:
        if company_id:
            await _cleanup_admin_workspace(email, company_id)
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM plans WHERE code = :code"), {"code": plan_code})
            await db.commit()
