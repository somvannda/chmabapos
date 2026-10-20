from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import BillingReminder, EmailSend, EmailSuppression, Notification, Subscription
from app.services.billing_emails import BILLING_REMINDER_SOURCE
from app.services.mailing import MAX_SEND_LIMIT, send_pending_emails
from app.services.reminders import run_reminder_job

EMAIL_SUFFIX = "remind"


async def create_paid_workspace(client: AsyncClient, email: str, ends_at: datetime) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Reminder Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Reminder Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    workspace = setup.json()
    async with SessionLocal() as db:
        sub_id = (
            await db.execute(text("SELECT id FROM subscriptions WHERE company_id = :company_id"), {"company_id": workspace["company"]["id"]})
        ).scalar_one()
        await db.execute(text("UPDATE subscriptions SET status = 'canceled' WHERE id = :sub_id"), {"sub_id": sub_id})
        db.add(
            Subscription(
                company_id=uuid.UUID(workspace["company"]["id"]),
                plan_code="pro",
                billing_cycle="monthly",
                status="active",
                starts_at=datetime.now(timezone.utc) - timedelta(days=20),
                ends_at=ends_at,
            )
        )
        await db.commit()
    return workspace, headers


async def cleanup(emails: list[str], company_id: str | None) -> None:
    async with SessionLocal() as db:
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM notifications USING stores WHERE notifications.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM billing_reminders USING subscriptions WHERE billing_reminders.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
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
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
            await db.execute(text("DELETE FROM email_suppressions WHERE email = :email"), {"email": email})
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_reminder_job_sends_once_per_bucket_and_notifies_owners() -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_paid_workspace(client, email, datetime.now(timezone.utc) + timedelta(days=5))
            company_id = workspace["company"]["id"]
        async with SessionLocal() as db:
            first = await run_reminder_job(db)
            await db.commit()
        assert first["reminders"] == 1
        async with SessionLocal() as db:
            sub = (
                await db.execute(
                    select(Subscription).where(Subscription.company_id == uuid.UUID(company_id), Subscription.plan_code == "pro", Subscription.status == "active")
                )
            ).scalars().first()
            sent = (await db.execute(select(BillingReminder).where(BillingReminder.subscription_id == sub.id))).scalars().all()
            assert len(sent) == 1
            owner_id = await db.scalar(text("SELECT user_id FROM memberships WHERE company_id = :company_id AND role = 'owner'"), {"company_id": company_id})
            notifications = (
                await db.execute(select(Notification).where(Notification.user_id == owner_id, Notification.type == "billing"))
            ).scalars().all()
            assert len(notifications) == 1

        async with SessionLocal() as db:
            second = await run_reminder_job(db)
            await db.commit()
        assert second["reminders"] == 0
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_no_reminder_until_within_horizon() -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_paid_workspace(client, email, datetime.now(timezone.utc) + timedelta(days=45))
            company_id = workspace["company"]["id"]
        async with SessionLocal() as db:
            result = await run_reminder_job(db)
            await db.commit()
        assert result["reminders"] == 0
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_grace_reminder_fires_once_after_period_ends() -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_paid_workspace(client, email, datetime.now(timezone.utc) - timedelta(hours=1))
            company_id = workspace["company"]["id"]
        async with SessionLocal() as db:
            first = await run_reminder_job(db)
            await db.commit()
        assert first["reminders"] == 1
        async with SessionLocal() as db:
            sub = (
                await db.execute(
                    select(Subscription).where(Subscription.company_id == uuid.UUID(company_id), Subscription.plan_code == "pro", Subscription.status == "active")
                )
            ).scalars().first()
            sent = (await db.execute(select(BillingReminder).where(BillingReminder.subscription_id == sub.id))).scalars().all()
            assert [reminder.days_before for reminder in sent] == [0]
        async with SessionLocal() as db:
            second = await run_reminder_job(db)
            await db.commit()
        assert second["reminders"] == 0
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_reminder_links_the_owner_into_billing_and_queues_the_email() -> None:
    """A reminder is actionable and durable: the bell row and the outbox email
    both open Billing on the right plan.

    The link is a relative path (the account segment is only known on the client)
    carrying the next plan, cycle and `pay` so the page mints a fresh KHQR on
    arrival instead of shipping one that would expire before the reminder lands.
    The email goes to the outbox rather than inline, so a mail outage retries it.
    """
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_paid_workspace(client, email, datetime.now(timezone.utc) + timedelta(days=5))
            company_id = workspace["company"]["id"]
        async with SessionLocal() as db:
            await run_reminder_job(db)
            await db.commit()

        expected = "billing?renew=pro&cycle=monthly&pay=1"
        async with SessionLocal() as db:
            owner_id = await db.scalar(text("SELECT user_id FROM memberships WHERE company_id = :company_id AND role = 'owner'"), {"company_id": company_id})
            notification = (
                await db.execute(select(Notification).where(Notification.user_id == owner_id, Notification.type == "billing"))
            ).scalars().one()
        assert notification.link == expected

        # The API hands the same destination to the web client.
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listing = await client.get("/api/v1/notifications", headers=headers)
        assert listing.status_code == 200
        billing_rows = [row for row in listing.json() if row["type"] == "billing"]
        assert billing_rows and billing_rows[0]["link"] == expected

        # The email is queued, not sent inline, and carries the same destination
        # made absolute for this workspace (attribute-escaped, so `&` is `&amp;`).
        async with SessionLocal() as db:
            queued = (
                await db.execute(
                    select(EmailSend).where(EmailSend.recipient_email == email, EmailSend.source == BILLING_REMINDER_SOURCE)
                )
            ).scalars().all()
        assert len(queued) == 1
        assert queued[0].status == "queued"
        assert "/billing?renew=pro&amp;cycle=monthly&amp;pay=1" in queued[0].body_html
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_a_later_reminder_replaces_the_bell_row_instead_of_stacking() -> None:
    """-7 then -3 is one current nudge, not two stale ones."""
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_paid_workspace(client, email, datetime.now(timezone.utc) + timedelta(days=5))
            company_id = workspace["company"]["id"]
        async with SessionLocal() as db:
            first = await run_reminder_job(db)
            await db.commit()
        assert first["reminders"] == 1

        # Two days later the -3 day nudge also becomes due.
        async with SessionLocal() as db:
            await db.execute(
                text("UPDATE subscriptions SET ends_at = :ends WHERE company_id = :company_id AND plan_code = 'pro' AND status = 'active'"),
                {"ends": datetime.now(timezone.utc) + timedelta(days=2), "company_id": company_id},
            )
            await db.commit()
        async with SessionLocal() as db:
            second = await run_reminder_job(db)
            await db.commit()
        assert second["reminders"] == 1

        async with SessionLocal() as db:
            owner_id = await db.scalar(text("SELECT user_id FROM memberships WHERE company_id = :company_id AND role = 'owner'"), {"company_id": company_id})
            notifications = (
                await db.execute(select(Notification).where(Notification.user_id == owner_id, Notification.type == "billing"))
            ).scalars().all()
        assert len(notifications) == 1, "the bell keeps one current reminder, not a stack"
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_paying_clears_the_renewal_reminder() -> None:
    """Once the plan is paid the nudge is stale, so the bell must drop it."""
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_paid_workspace(client, email, datetime.now(timezone.utc) + timedelta(days=5))
            company_id = workspace["company"]["id"]
        async with SessionLocal() as db:
            await run_reminder_job(db)
            await db.commit()
        async with SessionLocal() as db:
            owner_id = await db.scalar(text("SELECT user_id FROM memberships WHERE company_id = :company_id AND role = 'owner'"), {"company_id": company_id})
            assert (await db.execute(select(Notification).where(Notification.user_id == owner_id, Notification.type == "billing"))).scalars().all()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            checkout = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
            assert checkout.status_code == 201
            external_id = checkout.json()["payment"]["external_id"]
            done = await client.post(f"/api/v1/mock/chamabapay/{external_id}/complete", headers=headers)
            assert done.status_code == 204

        async with SessionLocal() as db:
            owner_id = await db.scalar(text("SELECT user_id FROM memberships WHERE company_id = :company_id AND role = 'owner'"), {"company_id": company_id})
            remaining = (
                await db.execute(select(Notification).where(Notification.user_id == owner_id, Notification.type == "billing"))
            ).scalars().all()
        assert remaining == [], "a paid plan should not leave a renewal reminder behind"
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_reminder_email_is_transactional_not_marketing(monkeypatch) -> None:
    """A suppressed owner still gets the reminder: billing mail ignores the
    marketing unsubscribe list, because the store's own subscription is its
    control and losing a renewal notice is worse than one extra send."""
    delivered: list[str] = []

    async def fake_send(recipient, subject, body, **kwargs):
        delivered.append(recipient)
        return True, None

    async def fake_marketing(*args, **kwargs):
        return True, None

    monkeypatch.setattr("app.services.mailing.send_email_with_id", fake_send)
    monkeypatch.setattr("app.services.mailing.send_marketing_email_with_id", fake_marketing)

    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_paid_workspace(client, email, datetime.now(timezone.utc) + timedelta(days=5))
            company_id = workspace["company"]["id"]
        async with SessionLocal() as db:
            await run_reminder_job(db)
            db.add(EmailSuppression(email=email, reason="unsubscribed"))
            await db.commit()
        async with SessionLocal() as db:
            stats = await send_pending_emails(db, limit=MAX_SEND_LIMIT)
        assert stats["sent"] >= 1
        async with SessionLocal() as db:
            row = (
                await db.execute(
                    select(EmailSend).where(EmailSend.recipient_email == email, EmailSend.source == BILLING_REMINDER_SOURCE)
                )
            ).scalars().one()
        assert row.status == "sent", "the reminder must not be skipped as marketing"
        assert email in delivered
    finally:
        await cleanup([email], company_id)
