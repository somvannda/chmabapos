"""GET /billing/subscription reports the plan actually in force."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import SessionLocal
from app.main import app
from app.models import Subscription
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_current_subscription_prefers_the_in_force_plan() -> None:
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Current Sub Store", "Main", plan="starter", email_prefix="current-sub")
            email, company_id = ctx["email"], ctx["company_id"]
            headers = ctx["headers"]

            now = datetime.now(timezone.utc)
            async with SessionLocal() as db:
                # A newer pending upgrade must not be reported as the current plan.
                db.add(
                    Subscription(
                        company_id=uuid.UUID(company_id),
                        plan_code="pro",
                        billing_cycle="monthly",
                        status="pending",
                        starts_at=now,
                        ends_at=None,
                        created_at=now + timedelta(seconds=5),
                    )
                )
                await db.commit()

            current = await client.get("/api/v1/billing/subscription", headers=headers)
            assert current.status_code == 200, current.text
            assert current.json()["plan_code"] == "starter"
            assert current.json()["status"] == "active"
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
