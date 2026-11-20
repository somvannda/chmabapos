"""A catalog price edit warns in-force subscribers before their next renewal."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.billing import plan_terms
from app.db import SessionLocal
from app.main import app
from app.models import EmailSend, Plan, Subscription
from app.services.billing_emails import BILLING_PRICE_CHANGE_SOURCE
from tests.test_admin_subscription_management import _admin_headers, _cleanup, _free_workspace, _promote_super


@pytest.mark.asyncio
async def test_price_edit_queues_a_notice_for_in_force_subscribers() -> None:
    email = f"price-notice-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    plan_code = f"price-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace = await _free_workspace(client, email)
            company_id = workspace["company"]["id"]

        await _promote_super(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin = await _admin_headers(client, email)
            created = await client.post(
                "/api/v1/admin/plans",
                headers=admin,
                json={
                    "code": plan_code,
                    "name": "Notice plan",
                    "monthly_price": 10,
                    "max_stores": 1,
                    "max_members": 2,
                },
            )
            assert created.status_code == 201, created.text

            async with SessionLocal() as db:
                plan = await db.get(Plan, plan_code)
                assert plan is not None
                db.add(
                    Subscription(
                        company_id=uuid.UUID(company_id),
                        plan_code=plan_code,
                        billing_cycle="monthly",
                        status="active",
                        starts_at=now - timedelta(days=1),
                        ends_at=now + timedelta(days=10),
                        plan_terms=plan_terms(plan),
                    )
                )
                await db.commit()

            updated = await client.patch(
                f"/api/v1/admin/plans/{plan_code}",
                headers=admin,
                json={"monthly_price": 12},
            )
            assert updated.status_code == 200, updated.text

        async with SessionLocal() as db:
            queued = (
                await db.execute(
                    select(EmailSend).where(
                        EmailSend.company_id == uuid.UUID(company_id),
                        EmailSend.source == BILLING_PRICE_CHANGE_SOURCE,
                    )
                )
            ).scalars().all()
            assert len(queued) == 1
            assert queued[0].recipient_email == email
            assert queued[0].status == "queued"
            assert "$10.00" in queued[0].body_html
            assert "$12.00" in queued[0].body_html
            assert "Nothing changes before" in queued[0].body_html
            assert "12.00" in queued[0].subject

            details = await db.scalar(
                text(
                    "SELECT details FROM audit_logs WHERE action = 'admin.plan_updated' "
                    "AND details->>'code' = :code ORDER BY created_at DESC LIMIT 1"
                ),
                {"code": plan_code},
            )
            assert details["price_change_notified"] == 1
    finally:
        if company_id:
            async with SessionLocal() as db:
                await db.execute(
                    text("DELETE FROM email_sends WHERE company_id = :company_id"),
                    {"company_id": company_id},
                )
                await db.commit()
        async with SessionLocal() as db:
            # Plan audits have no company entity, so clear the actor rows before
            # ``_cleanup`` deletes the user (audit_logs.actor_user_id is FK).
            await db.execute(
                text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email = :email)"),
                {"email": email},
            )
            await db.commit()
        await _cleanup(email, company_id)
        async with SessionLocal() as db:
            await db.execute(
                text("DELETE FROM audit_logs WHERE details->>'code' = :code"),
                {"code": plan_code},
            )
            await db.execute(text("DELETE FROM plans WHERE code = :code"), {"code": plan_code})
            await db.commit()


@pytest.mark.asyncio
async def test_unchanged_price_does_not_queue_a_notice() -> None:
    email = f"price-notice-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    plan_code = f"price-{uuid.uuid4().hex[:6]}"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace = await _free_workspace(client, email)
            company_id = workspace["company"]["id"]
        await _promote_super(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin = await _admin_headers(client, email)
            created = await client.post(
                "/api/v1/admin/plans",
                headers=admin,
                json={"code": plan_code, "name": "Same plan", "monthly_price": 10, "max_stores": 1, "max_members": 2},
            )
            assert created.status_code == 201, created.text
            # A limits-only edit must not look like a price change.
            await client.patch(f"/api/v1/admin/plans/{plan_code}", headers=admin, json={"max_stores": 2})
        async with SessionLocal() as db:
            count = await db.scalar(
                select(EmailSend).where(
                    EmailSend.company_id == uuid.UUID(company_id),
                    EmailSend.source == BILLING_PRICE_CHANGE_SOURCE,
                )
            )
            assert count is None
    finally:
        async with SessionLocal() as db:
            await db.execute(
                text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email = :email)"),
                {"email": email},
            )
            await db.commit()
        await _cleanup(email, company_id)
        async with SessionLocal() as db:
            await db.execute(
                text("DELETE FROM audit_logs WHERE details->>'code' = :code"),
                {"code": plan_code},
            )
            await db.execute(text("DELETE FROM plans WHERE code = :code"), {"code": plan_code})
            await db.commit()
