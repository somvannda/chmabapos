"""Regression tests for the hardened prepaid billing engine.

Covers the Phase 0/1 guarantees:

* pricing is derived from the canonical monthly price in one place;
* a checkout snapshots the plan/cycle/price it bought (immutable history);
* fulfillment is idempotent across webhook replays and a terminal payment
  status is never rewritten;
* every forced capacity pause/restore is recorded in the audit trail.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.api.v1 import fulfill_billing_payment
from app.billing import load_entitlement
from app.db import SessionLocal
from app.main import app
from app.models import BillingPayment, BillingReceipt, Plan, Subscription, SubscriptionCapacityAction
from app.services.billing_lifecycle import restore_capacity, run_expiry_job
from app.services.pricing import cycle_days, period_end, period_total


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
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Billing Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Billing Immutability Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json(), headers


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
        await db.execute(text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


async def create_checkout(client: AsyncClient, headers: dict, plan_code: str, billing_cycle: str) -> dict:
    response = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": plan_code, "billing_cycle": billing_cycle})
    assert response.status_code == 201
    return response.json()


def test_pricing_is_derived_from_the_monthly_price() -> None:
    monthly = Decimal("4.99")
    assert period_total(monthly, "monthly") == monthly
    assert period_total(monthly, "semi_annual") == (monthly * 6 * Decimal("0.85")).quantize(Decimal("0.01"))
    assert period_total(monthly, "annual") == (monthly * 12 * Decimal("0.80")).quantize(Decimal("0.01"))
    assert cycle_days("monthly") == 30
    assert cycle_days("annual") == 365


@pytest.mark.asyncio
async def test_checkout_snapshots_plan_cycle_and_price(monkeypatch) -> None:
    email = f"billing-snapshot-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            monkeypatch.setattr("app.api.v1.cutluy_client_for", _fake_cutluy_factory)
            checkout = await create_checkout(client, headers, "starter", "annual")
            external_id = checkout["payment"]["external_id"]

        async with SessionLocal() as db:
            plan = await db.get(Plan, "starter")
            expected = period_total(plan.monthly_price, "annual")
            row = await db.scalar(select(BillingPayment).where(BillingPayment.external_id == external_id))
            assert row is not None
            assert row.company_id == uuid.UUID(company_id)
            assert row.plan_code == "starter"
            assert row.billing_cycle == "annual"
            assert row.amount == expected
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_fulfillment_replay_activates_once(monkeypatch) -> None:
    email = f"billing-replay-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            monkeypatch.setattr("app.api.v1.cutluy_client_for", _fake_cutluy_factory)
            checkout = await create_checkout(client, headers, "starter", "monthly")
            external_id = checkout["payment"]["external_id"]
            reference_id = checkout["payment"]["reference_id"]

        async with SessionLocal() as db:
            for _ in range(3):
                await fulfill_billing_payment(external_id, reference_id, None, db)
                await db.commit()

        async with SessionLocal() as db:
            active = (
                await db.execute(
                    select(Subscription).where(
                        Subscription.company_id == uuid.UUID(company_id),
                        Subscription.plan_code == "starter",
                        Subscription.status == "active",
                    )
                )
            ).scalars().all()
            assert len(active) == 1
            ends_at = active[0].ends_at
            assert ends_at is not None
            payment = await db.scalar(select(BillingPayment).where(BillingPayment.external_id == external_id))
            assert payment.fulfilled_at is not None
            assert payment.period_start is not None
            assert payment.period_end == ends_at

        # A late duplicate cannot extend the period again.
        async with SessionLocal() as db:
            await fulfill_billing_payment(external_id, reference_id, None, db)
            await db.commit()
        async with SessionLocal() as db:
            active = (
                await db.execute(
                    select(Subscription).where(
                        Subscription.company_id == uuid.UUID(company_id),
                        Subscription.plan_code == "starter",
                        Subscription.status == "active",
                    )
                )
            ).scalars().all()
            assert len(active) == 1
            assert active[0].ends_at == ends_at
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_webhook_replay_activates_once_and_status_is_terminal(monkeypatch) -> None:
    email = f"billing-webhook-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            monkeypatch.setattr("app.api.v1.cutluy_client_for", _fake_cutluy_factory)
            checkout = await create_checkout(client, headers, "starter", "monthly")
            external_id = checkout["payment"]["external_id"]
            reference_id = checkout["payment"]["reference_id"]
            amount = checkout["payment"]["amount"]

        def event(status: str) -> dict:
            return {
                "id": f"evt_{uuid.uuid4().hex}",
                "type": "payment.paid",
                "created": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "payment": {
                        "id": external_id,
                        "status": status,
                        "amount": str(amount),
                        "currency": "USD",
                        "reference_id": reference_id,
                        "approved_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            }

        monkeypatch.setattr("app.api.v1.signature_is_valid", lambda *args, **kwargs: True)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(3):
                response = await client.post("/api/v1/webhooks/cutluy", json=event("paid"))
                assert response.status_code == 204
            # A later non-paid event must not rewrite the terminal paid status.
            response = await client.post("/api/v1/webhooks/cutluy", json=event("expired"))
            assert response.status_code == 204

        async with SessionLocal() as db:
            payment = await db.scalar(select(BillingPayment).where(BillingPayment.external_id == external_id))
            assert payment.status == "paid"
            active = (
                await db.execute(
                    select(Subscription).where(
                        Subscription.company_id == uuid.UUID(company_id),
                        Subscription.plan_code == "starter",
                        Subscription.status == "active",
                    )
                )
            ).scalars().all()
            assert len(active) == 1
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_capacity_actions_are_audited_and_reversible() -> None:
    email = f"billing-audit-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            await replace_subscription(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=30))
            created = []
            for name in ("Branch 2", "Branch 3"):
                response = await client.post("/api/v1/stores", headers=headers, json={"name": name, "currency_code": "USD"})
                assert response.status_code == 201
                created.append(response.json()["id"])
            await replace_subscription(company_id, "pro", datetime.now(timezone.utc) - timedelta(days=3))

        async with SessionLocal() as db:
            stats = await run_expiry_job(db)
            await db.commit()
        assert stats["paused_stores"] == 2

        async with SessionLocal() as db:
            pauses = (
                await db.execute(
                    select(SubscriptionCapacityAction).where(
                        SubscriptionCapacityAction.company_id == uuid.UUID(company_id),
                        SubscriptionCapacityAction.action == "pause",
                    )
                )
            ).scalars().all()
            assert len(pauses) == 2
            assert {str(row.resource_id) for row in pauses} == set(created)
            assert all(row.reason == "expiry" for row in pauses)
            assert all(row.restored_at is None for row in pauses)
            fallback = (
                await db.execute(
                    select(Subscription).where(
                        Subscription.company_id == uuid.UUID(company_id),
                        Subscription.status == "active",
                        Subscription.plan_code == "free",
                    )
                )
            ).scalars().first()
            paused_store_ids = list(fallback.paused_store_ids or [])

        async with SessionLocal() as db:
            await replace_subscription(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=29))
        async with SessionLocal() as db:
            plan = await db.get(Plan, "pro")
            pro = (
                await db.execute(
                    select(Subscription).where(
                        Subscription.company_id == uuid.UUID(company_id),
                        Subscription.plan_code == "pro",
                        Subscription.status == "active",
                    )
                )
            ).scalars().first()
            restored = await restore_capacity(
                db, uuid.UUID(company_id), plan=plan, store_ids=paused_store_ids, subscription=pro, reason="upgrade"
            )
            assert restored["stores"] == 2
            await db.commit()

        async with SessionLocal() as db:
            pauses = (
                await db.execute(
                    select(SubscriptionCapacityAction).where(
                        SubscriptionCapacityAction.company_id == uuid.UUID(company_id),
                        SubscriptionCapacityAction.action == "pause",
                    )
                )
            ).scalars().all()
            assert len(pauses) == 2
            assert all(row.restored_at is not None for row in pauses)
            restores = (
                await db.execute(
                    select(SubscriptionCapacityAction).where(
                        SubscriptionCapacityAction.company_id == uuid.UUID(company_id),
                        SubscriptionCapacityAction.action == "restore",
                    )
                )
            ).scalars().all()
            assert len(restores) == 2
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_fulfillment_issues_one_immutable_receipt(monkeypatch) -> None:
    email = f"billing-receipt-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            monkeypatch.setattr("app.api.v1.cutluy_client_for", _fake_cutluy_factory)
            checkout = await create_checkout(client, headers, "starter", "annual")
            external_id = checkout["payment"]["external_id"]
            reference_id = checkout["payment"]["reference_id"]

        async with SessionLocal() as db:
            for _ in range(3):
                await fulfill_billing_payment(external_id, reference_id, None, db)
                await db.commit()

        async with SessionLocal() as db:
            receipts = (
                await db.execute(select(BillingReceipt).where(BillingReceipt.company_id == uuid.UUID(company_id)))
            ).scalars().all()
            assert len(receipts) == 1
            receipt = receipts[0]
            assert receipt.receipt_number.startswith("CHM-")
            assert receipt.plan_code == "starter"
            assert receipt.billing_cycle == "annual"
            assert receipt.provider == "cutluy"
            payment = await db.scalar(select(BillingPayment).where(BillingPayment.external_id == external_id))
            assert receipt.amount == payment.amount
            assert receipt.period_start == payment.period_start
            assert receipt.period_end == payment.period_end
            receipt_number = receipt.receipt_number

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/billing/receipts", headers=headers)
            assert response.status_code == 200
            rows = response.json()
            assert len(rows) == 1
            assert rows[0]["receipt_number"] == receipt_number
            assert rows[0]["plan_code"] == "starter"
    finally:
        await cleanup(email, company_id)


def test_calendar_period_end_clamps_short_months() -> None:
    jan_31 = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
    assert period_end(jan_31, "monthly") == datetime(2026, 2, 28, 12, tzinfo=timezone.utc)
    assert period_end(jan_31, "semi_annual") == datetime(2026, 7, 31, 12, tzinfo=timezone.utc)
    assert period_end(jan_31, "annual") == datetime(2027, 1, 31, 12, tzinfo=timezone.utc)
    jan_10 = datetime(2026, 1, 10, 9, tzinfo=timezone.utc)
    assert period_end(jan_10, "monthly") == datetime(2026, 2, 10, 9, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_grace_window_delays_free_fallback() -> None:
    email = f"billing-grace-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        # Ended 1 day ago: still inside the 48h grace, so pro still governs.
        await replace_subscription(company_id, "pro", datetime.now(timezone.utc) - timedelta(days=1))
        async with SessionLocal() as db:
            ent = await load_entitlement(db, uuid.UUID(company_id))
            assert ent.plan.code == "pro"
            assert ent.expired is None
        async with SessionLocal() as db:
            stats = await run_expiry_job(db)
            await db.commit()
        assert stats["expired_subs"] == 0
        # Push past grace; the Free fallback now runs.
        async with SessionLocal() as db:
            await db.execute(
                text("UPDATE subscriptions SET ends_at = now() - interval '3 days' WHERE company_id = :company_id AND status = 'active'"),
                {"company_id": company_id},
            )
            await db.commit()
        async with SessionLocal() as db:
            stats = await run_expiry_job(db)
            await db.commit()
        assert stats["expired_subs"] >= 1
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_admin_can_record_billing_refund(monkeypatch) -> None:
    email = f"billing-refund-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            monkeypatch.setattr("app.api.v1.cutluy_client_for", _fake_cutluy_factory)
            checkout = await create_checkout(client, headers, "starter", "monthly")
            external_id = checkout["payment"]["external_id"]
            reference_id = checkout["payment"]["reference_id"]
            payment_id = checkout["payment"]["id"]
        async with SessionLocal() as db:
            await fulfill_billing_payment(external_id, reference_id, None, db)
            await db.commit()
        async with SessionLocal() as db:
            await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": email})
            await db.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            recorded = await client.post(
                f"/api/v1/admin/billing-payments/{payment_id}/refund",
                headers=admin_headers,
                json={"amount": "0.50", "reason": "goodwill"},
            )
            assert recorded.status_code == 201
            assert recorded.json()["amount"] == "0.50"
            assert recorded.json()["company_id"] == company_id
            too_much = await client.post(
                f"/api/v1/admin/billing-payments/{payment_id}/refund",
                headers=admin_headers,
                json={"amount": "99.00"},
            )
            assert too_much.status_code == 400
    finally:
        await cleanup(email, company_id)
