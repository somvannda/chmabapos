"""An upgrade must not throw away an already-paid future renewal period."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Subscription
from app.services.pricing import period_end
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_upgrade_carries_the_stacked_prepaid_period_forward() -> None:
    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Carry Upgrade Co", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers = ctx["headers"]

            renewal = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "starter", "billing_cycle": "monthly"})
            assert renewal.status_code == 201, renewal.text
            completed = await client.post(f"/api/v1/mock/chamabapay/{renewal.json()['payment']['external_id']}/complete")
            assert completed.status_code == 204, completed.text

            async with SessionLocal() as db:
                rows = (
                    await db.execute(select(Subscription).where(Subscription.company_id == uuid.UUID(company_id)).order_by(Subscription.starts_at))
                ).scalars().all()
                active = [row for row in rows if row.status == "active" and row.plan_code == "starter"]
                assert len(active) == 2
                future = next(row for row in active if row.starts_at > datetime.now(timezone.utc))
                future_id = future.id
                carried = future.ends_at - future.starts_at if future.ends_at else None
                assert carried is not None

            upgrade = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": "pro", "billing_cycle": "monthly"})
            assert upgrade.status_code == 201, upgrade.text
            completed = await client.post(f"/api/v1/mock/chamabapay/{upgrade.json()['payment']['external_id']}/complete")
            assert completed.status_code == 204, completed.text

            async with SessionLocal() as db:
                pro = (
                    await db.execute(
                        select(Subscription).where(
                            Subscription.company_id == uuid.UUID(company_id),
                            Subscription.plan_code == "pro",
                            Subscription.status == "active",
                        )
                    )
                ).scalars().one()
                assert pro.ends_at == period_end(pro.starts_at, "monthly") + carried
                previous = await db.get(Subscription, future_id)
                assert previous is not None and previous.status == "canceled"
    finally:
        await cleanup_company(company_id, [email] if email else [])
