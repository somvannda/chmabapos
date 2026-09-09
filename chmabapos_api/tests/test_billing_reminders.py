from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import BillingReminder, Notification, Subscription
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
