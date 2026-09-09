from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.api.v1 import fulfill_billing_payment
from app.db import SessionLocal
from app.main import app
from app.models import BillingPayment, Subscription
from app.services.billing_lifecycle import run_expiry_job

EMAIL_SUFFIX = "schedule"


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Schedule Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Schedule Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
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


async def add_store(client: AsyncClient, headers: dict, name: str) -> str:
    response = await client.post("/api/v1/stores", headers=headers, json={"name": name, "currency_code": "USD"})
    assert response.status_code == 201
    return response.json()["id"]


async def make_pending_payment(company_id: str, plan_code: str, external_id: str) -> str:
    async with SessionLocal() as db:
        sub = Subscription(company_id=uuid.UUID(company_id), plan_code=plan_code, billing_cycle="monthly", status="pending", starts_at=datetime.now(timezone.utc))
        db.add(sub)
        await db.flush()
        db.add(
            BillingPayment(
                subscription_id=sub.id,
                amount=0,
                currency_code="USD",
                external_id=external_id,
                reference_id=f"plan-{uuid.uuid4().hex}",
                status="pending",
            )
        )
        await db.commit()
        return str(sub.id)


@pytest.mark.asyncio
async def test_schedule_validation_and_clear() -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            await activate_plan(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=30))

            over = await client.put("/api/v1/billing/schedule", headers=headers, json={"plan_code": "starter", "keep_store_ids": [], "keep_member_ids": []})
            assert over.status_code == 200
            assert over.json()["scheduled_plan_code"] == "starter"

            again = await client.put("/api/v1/billing/schedule", headers=headers, json={"plan_code": "starter"})
            assert again.status_code == 200
            assert again.json()["scheduled_plan_code"] == "starter"

            upgrade = await client.put("/api/v1/billing/schedule", headers=headers, json={"plan_code": "starter", "keep_member_ids": ["not-a-member"]})
            assert upgrade.status_code == 400

            cleared = await client.delete("/api/v1/billing/schedule", headers=headers)
            assert cleared.status_code == 200
            assert cleared.json()["scheduled_plan_code"] is None
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_upgrade_not_allowed_via_schedule() -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            await activate_plan(company_id, "starter", datetime.now(timezone.utc) + timedelta(days=30))
            response = await client.put("/api/v1/billing/schedule", headers=headers, json={"plan_code": "pro"})
            assert response.status_code == 400
            assert "checkout" in response.json()["detail"]
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_paid_downgrade_renewal_starts_at_boundary_and_applies_capacity() -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            store_ids = [workspace["store"]["id"]]
            await activate_plan(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=30))
            store_ids.append(await add_store(client, headers, "Branch B"))
            store_ids.append(await add_store(client, headers, "Branch C"))
            keep = store_ids[:2]

            scheduled = await client.put("/api/v1/billing/schedule", headers=headers, json={"plan_code": "starter", "keep_store_ids": keep})
            assert scheduled.status_code == 200
            assert scheduled.json()["scheduled_store_ids"] == keep

            external = f"mock_sched_{uuid.uuid4().hex}"
            await make_pending_payment(company_id, "starter", external)
            async with SessionLocal() as db:
                assert await fulfill_billing_payment(external, None, datetime.now(timezone.utc), db) is True
                await db.commit()
                pro = (
                    await db.execute(
                        select(Subscription).where(Subscription.company_id == uuid.UUID(company_id), Subscription.plan_code == "pro", Subscription.status == "active")
                    )
                ).scalars().first()
                assert pro is not None
                starter = (
                    await db.execute(
                        select(Subscription).where(Subscription.company_id == uuid.UUID(company_id), Subscription.plan_code == "starter", Subscription.status == "active")
                    )
                ).scalars().first()
                assert starter is not None
                assert starter.starts_at == pro.ends_at
                assert starter.ends_at == pro.ends_at + timedelta(days=30)
                assert starter.scheduled_store_ids == keep
                assert pro.scheduled_plan_code is None

                boundary = datetime.now(timezone.utc) - timedelta(days=1)
                await db.execute(text("UPDATE subscriptions SET ends_at = :boundary WHERE id = :sub_id"), {"boundary": boundary, "sub_id": pro.id})
                await db.execute(text("UPDATE subscriptions SET starts_at = :boundary WHERE id = :sub_id"), {"boundary": boundary, "sub_id": starter.id})
                await db.commit()
            async with SessionLocal() as db:
                await run_expiry_job(db)
                await db.commit()
            async with SessionLocal() as db:
                pro = (
                    await db.execute(
                        select(Subscription).where(Subscription.company_id == uuid.UUID(company_id), Subscription.plan_code == "pro")
                    )
                ).scalars().first()
                assert pro.status == "expired"
                starter = (
                    await db.execute(
                        select(Subscription).where(Subscription.company_id == uuid.UUID(company_id), Subscription.plan_code == "starter", Subscription.status == "active")
                    )
                ).scalars().first()
                assert starter is not None
                assert starter.scheduled_plan_code is None
                free_active = await db.scalar(
                    select(Subscription.id).where(Subscription.company_id == uuid.UUID(company_id), Subscription.plan_code == "free", Subscription.status == "active")
                )
                assert free_active is None
                active_ids = [
                    str(row.id)
                    for row in (await db.execute(text("SELECT id FROM stores WHERE company_id = :company_id AND is_active = TRUE"), {"company_id": company_id})).all()
                ]
                assert sorted(active_ids) == sorted(keep)
    finally:
        await cleanup([email], company_id)


@pytest.mark.asyncio
async def test_free_fallback_prefers_scheduled_keep_store() -> None:
    email = f"billing-{EMAIL_SUFFIX}-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            first_store = workspace["store"]["id"]
            await activate_plan(company_id, "pro", datetime.now(timezone.utc) + timedelta(days=30))
            second_store = await add_store(client, headers, "Branch B")
            scheduled = await client.put(
                "/api/v1/billing/schedule",
                headers=headers,
                json={"plan_code": "free", "keep_store_ids": [second_store], "keep_member_ids": []},
            )
            assert scheduled.status_code == 200
            async with SessionLocal() as db:
                pro = (
                    await db.execute(
                        select(Subscription).where(Subscription.company_id == uuid.UUID(company_id), Subscription.plan_code == "pro", Subscription.status == "active")
                    )
                ).scalars().first()
                await db.execute(text("UPDATE subscriptions SET ends_at = :boundary WHERE id = :sub_id"), {"boundary": datetime.now(timezone.utc) - timedelta(days=1), "sub_id": pro.id})
                await db.commit()
            async with SessionLocal() as db:
                await run_expiry_job(db)
                await db.commit()
            async with SessionLocal() as db:
                free = (
                    await db.execute(
                        select(Subscription).where(Subscription.company_id == uuid.UUID(company_id), Subscription.plan_code == "free", Subscription.status == "active")
                    )
                ).scalars().first()
                assert free is not None
                active_ids = [
                    str(row.id)
                    for row in (await db.execute(text("SELECT id FROM stores WHERE company_id = :company_id AND is_active = TRUE"), {"company_id": company_id})).all()
                ]
                assert active_ids == [second_store]
                assert first_store in (free.paused_store_ids or [])
    finally:
        await cleanup([email], company_id)

@pytest.mark.asyncio
async def test_same_plan_stacking_renewal_starts_at_boundary_and_extends() -> None:
    email = f"billing-stack-{uuid.uuid4().hex[:8]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            ends = datetime.now(timezone.utc) + timedelta(days=30)
            await activate_plan(company_id, "pro", ends)
            now = datetime.now(timezone.utc)

            first_external = f"mock_stack_1_{uuid.uuid4().hex}"
            await make_pending_payment(company_id, "pro", first_external)
            async with SessionLocal() as db:
                assert await fulfill_billing_payment(first_external, None, now, db) is True
                await db.commit()
                rows = (
                    await db.execute(
                        select(Subscription).where(Subscription.company_id == uuid.UUID(company_id), Subscription.plan_code == "pro", Subscription.status == "active")
                    )
                ).scalars().all()
                assert len(rows) == 2
                current = next(row for row in rows if row.ends_at > now)
                stacked = next(row for row in rows if row.starts_at > now)
                assert current.ends_at == ends
                assert stacked.starts_at == ends
                assert stacked.ends_at == ends + timedelta(days=30)
                stacked_id = str(stacked.id)

            second_external = f"mock_stack_2_{uuid.uuid4().hex}"
            second_id = await make_pending_payment(company_id, "pro", second_external)
            async with SessionLocal() as db:
                assert await fulfill_billing_payment(second_external, None, datetime.now(timezone.utc), db) is True
                await db.commit()
                stacked = await db.get(Subscription, uuid.UUID(stacked_id))
                assert stacked is not None
                assert stacked.ends_at == ends + timedelta(days=60)
                canceled_second = await db.get(Subscription, uuid.UUID(second_id))
                assert canceled_second.status == "canceled"
                payment = (
                    await db.execute(select(BillingPayment).where(BillingPayment.external_id == second_external))
                ).scalars().first()
                assert payment is not None and payment.subscription_id == stacked.id
    finally:
        await cleanup([email], company_id)
