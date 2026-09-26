"""Scheduled payment reconciliation: self-heal payments a missed webhook left open.

A dropped ChmabaPay webhook must not leave a paying merchant unactivated. The
job re-checks open plan payments against the provider and routes a PAID result
through the idempotent fulfilment path.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text

from app.api import v1
from app.db import SessionLocal
from app.main import app
from app.models import BillingPayment, BillingReceipt, Subscription
from app.services.payments.base import PaymentProviderError


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Reconcile Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Reconcile Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json(), headers


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
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


async def make_pending_payment(company_id: str, plan_code: str, external_id: str, *, age_minutes: int = 10) -> str:
    async with SessionLocal() as db:
        subscription = Subscription(
            company_id=uuid.UUID(company_id),
            plan_code=plan_code,
            billing_cycle="monthly",
            status="pending",
            starts_at=datetime.now(timezone.utc),
        )
        db.add(subscription)
        await db.flush()
        db.add(
            BillingPayment(
                subscription_id=subscription.id,
                company_id=uuid.UUID(company_id),
                plan_code=plan_code,
                billing_cycle="monthly",
                provider="chamabapay",
                amount=Decimal("0.99"),
                currency_code="USD",
                external_id=external_id,
                reference_id=f"plan-{uuid.uuid4().hex}",
                status="pending",
                provider_metadata={"type": "subscription"},
                created_at=datetime.now(timezone.utc) - timedelta(minutes=age_minutes),
            )
        )
        await db.commit()
        return str(subscription.id)


class _FakeProvider:
    name = "chamabapay"

    def __init__(self, statuses: dict[str, str]) -> None:
        self.statuses = statuses
        self.calls: list[str] = []

    async def reconcile(self, external_id: str) -> dict:
        self.calls.append(external_id)
        if external_id not in self.statuses:
            raise PaymentProviderError("provider unavailable")
        return {"status": self.statuses[external_id], "source": None}


def _patch_provider(monkeypatch: pytest.MonkeyPatch, provider: _FakeProvider) -> None:
    async def fake_provider(_db):  # type: ignore[no-untyped-def]
        return provider

    monkeypatch.setattr(v1, "active_payment_provider", fake_provider)


async def _receipt_count(company_id: str) -> int:
    async with SessionLocal() as db:
        return await db.scalar(select(func.count(BillingReceipt.id)).where(BillingReceipt.company_id == uuid.UUID(company_id))) or 0


@pytest.mark.asyncio
async def test_reconcile_activates_paid_billing_payment_once(monkeypatch) -> None:
    email = f"reconcile-paid-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        external = f"mock_{uuid.uuid4().hex}"
        await make_pending_payment(company_id, "starter", external, age_minutes=10)
        _patch_provider(monkeypatch, _FakeProvider({external: "PAID"}))

        async with SessionLocal() as db:
            stats = await v1.reconcile_pending_billing_payments(db)
        assert stats["activated"] == 1

        async with SessionLocal() as db:
            payment = await db.scalar(select(BillingPayment).where(BillingPayment.external_id == external))
            assert payment is not None and payment.status == "paid" and payment.fulfilled_at is not None
            subscription = await db.get(Subscription, payment.subscription_id)
            assert subscription is not None and subscription.status == "active" and subscription.ends_at is not None
        assert await _receipt_count(company_id) == 1

        # Re-running must not double-activate.
        async with SessionLocal() as db:
            again = await v1.reconcile_pending_billing_payments(db)
        assert again["activated"] == 0
        assert await _receipt_count(company_id) == 1
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_reconcile_marks_failed_terminal(monkeypatch) -> None:
    email = f"reconcile-failed-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        external = f"mock_{uuid.uuid4().hex}"
        await make_pending_payment(company_id, "starter", external, age_minutes=10)
        _patch_provider(monkeypatch, _FakeProvider({external: "FAILED"}))

        async with SessionLocal() as db:
            stats = await v1.reconcile_pending_billing_payments(db)
        assert stats["closed"] == 1
        async with SessionLocal() as db:
            payment = await db.scalar(select(BillingPayment).where(BillingPayment.external_id == external))
            assert payment is not None and payment.status == "failed" and payment.fulfilled_at is None
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_reconcile_skips_recent_payments(monkeypatch) -> None:
    email = f"reconcile-recent-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        external = f"mock_{uuid.uuid4().hex}"
        await make_pending_payment(company_id, "starter", external, age_minutes=0)
        provider = _FakeProvider({external: "PAID"})
        _patch_provider(monkeypatch, provider)

        async with SessionLocal() as db:
            await v1.reconcile_pending_billing_payments(db)
        # Other rows in the shared DB may be checked; ours must be skipped.
        assert external not in provider.calls
        async with SessionLocal() as db:
            payment = await db.scalar(select(BillingPayment).where(BillingPayment.external_id == external))
            assert payment is not None and payment.status == "pending" and payment.fulfilled_at is None
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_reconcile_survives_provider_error(monkeypatch) -> None:
    email = f"reconcile-error-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        external = f"mock_{uuid.uuid4().hex}"
        await make_pending_payment(company_id, "starter", external, age_minutes=10)
        # No status for this id -> reconcile raises, the job must not abort.
        provider = _FakeProvider({})
        _patch_provider(monkeypatch, provider)

        async with SessionLocal() as db:
            await v1.reconcile_pending_billing_payments(db)
        assert external in provider.calls
        async with SessionLocal() as db:
            payment = await db.scalar(select(BillingPayment).where(BillingPayment.external_id == external))
            assert payment is not None and payment.status == "pending" and payment.fulfilled_at is None
    finally:
        await cleanup(email, company_id)
