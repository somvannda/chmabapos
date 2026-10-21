from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.api.v1 import fulfill_billing_payment
from app.db import SessionLocal
from app.main import app
from app.models import BillingPayment, PlatformActivity, Subscription
from app.services.pricing import period_end

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
                "DELETE FROM platform_activities WHERE company_id = :company_id",
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
async def test_downgrade_checkout_rejected_unless_scheduled(monkeypatch) -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        # ChmabaPay (mock) is the provider; no stub needed
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]
            await activate_plan(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=30))

            downgrade = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly"})
            assert downgrade.status_code == 400
            assert "downgrade" in downgrade.json()["detail"]

            scheduled = await client.put("/api/v1/billing/schedule", headers=headers, json={"plan_code": "starter"})
            assert scheduled.status_code == 200

            renewal = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly"})
            assert renewal.status_code == 201
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_same_plan_renewal_checkout_still_allowed(monkeypatch) -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        # ChmabaPay (mock) is the provider; no stub needed
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]
            await activate_plan(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=30))

            renewal = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
            assert renewal.status_code == 201
            assert renewal.json()["subscription"]["plan_code"] == "pro"
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_cancel_pending_checkout_keeps_current_plan_and_blocks_late_payment(monkeypatch) -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        # ChmabaPay (mock) is the provider; no stub needed
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]
            await activate_plan(company_id, "starter", datetime.now(timezone.utc) + timedelta(days=30))

            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
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
                # A late "paid" event must not revive the canceled payment: it stays
                # expired and is never marked fulfilled (so it is not counted as
                # revenue or shown as a paid+fulfilled charge).
                replayed = await db.scalar(select(BillingPayment).where(BillingPayment.external_id == external_id))
                assert replayed.status == "expired"
                assert replayed.fulfilled_at is None
                assert replayed.provider_metadata.get("late_paid_reported_at")
                activity = await db.scalar(
                    select(PlatformActivity).where(
                        PlatformActivity.company_id == uuid.UUID(company_id),
                        PlatformActivity.event_type == "billing.late_paid_unapplied",
                    )
                )
                assert activity is not None
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_cancel_after_unpaid_onboarding_falls_back_to_free(monkeypatch) -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        # ChmabaPay (mock) is the provider; no stub needed
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
async def test_cancel_rejects_when_no_pending_checkout(monkeypatch) -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        # ChmabaPay (mock) is the provider; no stub needed
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]

            first = await client.delete("/api/v1/billing/checkout", headers=headers)
            assert first.status_code == 409

            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly"})
            assert checkout.status_code == 201
            cancelled = await client.delete("/api/v1/billing/checkout", headers=headers)
            assert cancelled.status_code == 200
            second = await client.delete("/api/v1/billing/checkout", headers=headers)
            assert second.status_code == 409
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_repeat_checkout_for_the_same_plan_reuses_the_open_payment() -> None:
    """A double click must not create a second QR/payment for one intent."""
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]
            await activate_plan(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=30))

            first = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
            assert first.status_code == 201
            second = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
            assert second.status_code == 201

            # The second call returns the checkout that is already open.
            assert first.json()["payment"]["id"] == second.json()["payment"]["id"]
            assert first.json()["payment"]["external_id"] == second.json()["payment"]["external_id"]

            payments = await client.get("/api/v1/billing/payments", headers=headers)
            assert payments.status_code == 200
            assert len([row for row in payments.json() if row["status"] in {"pending", "scanned"}]) == 1
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_new_checkout_expires_the_superseded_open_payment() -> None:
    """Switching cycle supersedes the old checkout instead of leaving it payable."""
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]
            await activate_plan(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=30))

            monthly = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
            assert monthly.status_code == 201
            monthly_id = monthly.json()["payment"]["id"]

            annual = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "annual"})
            assert annual.status_code == 201
            annual_id = annual.json()["payment"]["id"]
            assert monthly_id != annual_id

            payments = await client.get("/api/v1/billing/payments", headers=headers)
            by_id = {row["id"]: row for row in payments.json()}
            assert by_id[monthly_id]["status"] == "expired"
            assert by_id[annual_id]["status"] in {"pending", "scanned"}
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_paying_one_checkout_expires_other_open_checkouts() -> None:
    """A successful payment closes any other live checkout for the company.

    This is the safety net for rows created before the supersede fix (or by a
    race): a stale pending payment must not keep the modal open after the plan
    is already paid.
    """
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]
            await activate_plan(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=30))

            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
            assert checkout.status_code == 201
            paid_id = checkout.json()["payment"]["id"]
            external_id = checkout.json()["payment"]["external_id"]
            subscription_id = checkout.json()["payment"]["subscription_id"]

        async with SessionLocal() as db:
            db.add(
                BillingPayment(
                    subscription_id=uuid.UUID(subscription_id),
                    company_id=uuid.UUID(company_id),
                    provider="chamabapay",
                    status="pending",
                    amount=Decimal("0.99"),
                    currency_code="USD",
                    external_id=f"stale-{uuid.uuid4().hex}",
                    reference_id=f"stale-ref-{uuid.uuid4().hex}",
                    plan_code="pro",
                    billing_cycle="monthly",
                )
            )
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            done = await client.post(f"/api/v1/mock/chamabapay/{external_id}/complete", headers=headers)
            assert done.status_code == 204

        async with SessionLocal() as db:
            stale = (
                await db.execute(select(BillingPayment).where(BillingPayment.status == "pending", BillingPayment.company_id == uuid.UUID(company_id)))
            ).scalars().all()
            assert stale == [], "paying should leave no other open billing payment"
            paid = await db.get(BillingPayment, uuid.UUID(paid_id))
            assert paid.status == "paid"
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_checkout_reports_the_coverage_window_for_an_early_renewal() -> None:
    """The modal can say "Covers <from> - <until>": an early renewal starts at the
    current period's end, not today."""
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        ends_at = datetime.now(timezone.utc) + timedelta(days=10)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]
            await activate_plan(company_id, "pro", ends_at)
            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
            assert checkout.status_code == 201
            payment = checkout.json()["payment"]

        assert payment["covers_from"] is not None and payment["covers_until"] is not None
        covers_from = datetime.fromisoformat(payment["covers_from"])
        covers_until = datetime.fromisoformat(payment["covers_until"])
        assert covers_from == ends_at
        assert covers_until == period_end(ends_at, "monthly")
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_checkout_reports_a_window_starting_now_for_an_upgrade() -> None:
    """An upgrade activates immediately, so its coverage starts today."""
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        before = datetime.now(timezone.utc)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]
            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly"})
            assert checkout.status_code == 201
            payment = checkout.json()["payment"]
        after = datetime.now(timezone.utc)

        covers_from = datetime.fromisoformat(payment["covers_from"])
        covers_until = datetime.fromisoformat(payment["covers_until"])
        assert before <= covers_from <= after, "an upgrade starts when it is paid"
        assert covers_until == period_end(covers_from, "monthly")
    finally:
        await cleanup([email], company_id)

@pytest.mark.asyncio
async def test_expired_payment_cancels_pending_subscription(monkeypatch) -> None:
    """A failed QR must not leave a stale ``pending`` checkout behind."""
    monkeypatch.setattr("app.api.v1.signature_is_valid", lambda *args, **kwargs: True)
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]
            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
            assert checkout.status_code == 201
            payment = checkout.json()["payment"]
            event = {
                "id": f"evt_{uuid.uuid4().hex}",
                "type": "payment.test",
                "created": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "payment": {
                        "id": payment["external_id"],
                        "status": "expired",
                        "amount": str(payment["amount"]),
                        "currency": "USD",
                        "reference_id": payment["reference_id"],
                    }
                },
            }
            hook = await client.post("/api/v1/webhooks/chamabapay", json=event)
            assert hook.status_code == 200, hook.text
        async with SessionLocal() as db:
            subscriptions = (
                await db.execute(select(Subscription).where(Subscription.company_id == uuid.UUID(company_id)))
            ).scalars().all()
            pro = next(row for row in subscriptions if row.plan_code == "pro")
            assert pro.status == "canceled"
            assert pro.ends_at is not None
            assert all(row.status != "pending" for row in subscriptions)
    finally:
        await cleanup([email], company_id)
