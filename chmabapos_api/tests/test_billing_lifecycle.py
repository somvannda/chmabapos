from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import Membership, Notification, Plan, Subscription
from app.services.billing_lifecycle import restore_capacity, run_expiry_job

OWNER_EMAIL_SUFFIX = "expiry-owner"
STAFF_EMAIL_SUFFIX = "expiry-staff"


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Lifecycle Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Lifecycle Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
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


async def run_job() -> dict:
    async with SessionLocal() as db:
        stats = await run_expiry_job(db)
        await db.commit()
        return stats


@pytest.mark.asyncio
async def test_expiry_job_falls_back_to_free_and_pauses_extra_stores() -> None:
    owner_email = f"billing-{OWNER_EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, owner_email)
            company_id = workspace["company"]["id"]
            main_store_id = workspace["store"]["id"]
            await replace_subscription(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=30))
            created = []
            for name in ("Branch 2", "Branch 3"):
                response = await client.post("/api/v1/stores", headers=headers, json={"name": name, "currency_code": "USD"})
                assert response.status_code == 201
                created.append(response.json()["id"])
            await replace_subscription(company_id, "pro", datetime.now(timezone.utc) - timedelta(days=3))

        stats = await run_job()
        assert stats["expired_subs"] >= 1

        async with SessionLocal() as db:
            fallback = (
                await db.execute(
                    select(Subscription).where(
                        Subscription.company_id == uuid.UUID(company_id),
                        Subscription.status == "active",
                        Subscription.plan_code == "free",
                    )
                )
            ).scalars().first()
            assert fallback is not None
            assert sorted(fallback.paused_store_ids) == sorted(created)
            store_ids = (await db.execute(text("SELECT id, is_active FROM stores WHERE company_id = :company_id"), {"company_id": company_id})).all()
            active_ids = [str(row.id) for row in store_ids if row.is_active]
            assert active_ids == [main_store_id]

            paused_store_ids = list(fallback.paused_store_ids or [])
        async with SessionLocal() as db:
            await replace_subscription(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=29))
            plan = await db.get(Plan, "pro")
            restored = await restore_capacity(db, uuid.UUID(company_id), plan=plan, store_ids=paused_store_ids)
            assert restored["stores"] == 2
            await db.commit()
        async with SessionLocal() as db:
            store_count = await db.scalar(text("SELECT count(*) FROM stores WHERE company_id = :company_id AND is_active = TRUE"), {"company_id": company_id})
            assert store_count == 3
    finally:
        await cleanup([owner_email], company_id)


@pytest.mark.asyncio
async def test_expiry_revokes_staff_but_keeps_owners_and_restores_on_upgrade() -> None:
    owner_email = f"billing-{OWNER_EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    staff_email = f"billing-{STAFF_EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, owner_email)
            company_id = workspace["company"]["id"]
            register = await client.post("/api/v1/auth/register", json={"email": staff_email, "full_name": "Lifecycle Manager", "password": "strong-password"})
            assert register.status_code == 201
        async with SessionLocal() as db:
            staff_user_id = await db.scalar(text("SELECT id FROM users WHERE email = :email"), {"email": staff_email})
            staff_membership = Membership(company_id=uuid.UUID(company_id), user_id=uuid.UUID(str(staff_user_id)), role="manager", status="active")
            db.add(staff_membership)
            await db.commit()
            manager_membership_id = str(staff_membership.id)
        await replace_subscription(company_id, "pro", datetime.now(timezone.utc) - timedelta(days=3))
        await run_job()

        async with SessionLocal() as db:
            staff_status = await db.scalar(
                text("SELECT status FROM memberships WHERE id = :membership_id"), {"membership_id": manager_membership_id}
            )
            assert staff_status == "revoked"
            owner_status = await db.scalar(
                text("SELECT status FROM memberships WHERE company_id = :company_id AND role = 'owner'"), {"company_id": company_id}
            )
            assert owner_status == "active"
            fallback = (
                await db.execute(
                    select(Subscription).where(
                        Subscription.company_id == uuid.UUID(company_id),
                        Subscription.status == "active",
                        Subscription.plan_code == "free",
                    )
                )
            ).scalars().first()
            assert fallback.paused_member_ids == [manager_membership_id]
            paused_member_ids = list(fallback.paused_member_ids or [])

        async with SessionLocal() as db:
            await replace_subscription(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=29))
            plan = await db.get(Plan, "pro")
            restored = await restore_capacity(db, uuid.UUID(company_id), plan=plan, member_ids=paused_member_ids)
            assert restored["members"] == 1
            await db.commit()
        async with SessionLocal() as db:
            staff_status = await db.scalar(
                text("SELECT status FROM memberships WHERE id = :membership_id"), {"membership_id": manager_membership_id}
            )
            assert staff_status == "active"
    finally:
        await cleanup([owner_email, staff_email], company_id)


@pytest.mark.asyncio
async def test_expiry_notifies_owner_of_free_fallback() -> None:
    owner_email = f"billing-{OWNER_EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, owner_email)
            company_id = workspace["company"]["id"]
        await replace_subscription(company_id, "pro", datetime.now(timezone.utc) - timedelta(days=3))
        await run_job()
        async with SessionLocal() as db:
            owner_id = await db.scalar(
                text("SELECT user_id FROM memberships WHERE company_id = :company_id AND role = 'owner'"), {"company_id": company_id}
            )
            notifications = (
                await db.execute(
                    select(Notification).where(Notification.user_id == owner_id, Notification.type == "billing")
                )
            ).scalars().all()
            assert any("expired" in (notification.title or "").lower() for notification in notifications)
    finally:
        await cleanup([owner_email], company_id)
