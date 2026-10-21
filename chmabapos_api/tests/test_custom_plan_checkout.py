"""Plans created by the platform admin must be purchasable and renewable."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.models import Plan
from tests.test_billing_checkout_cancel import cleanup, register_workspace


@pytest.mark.asyncio
async def test_custom_plan_can_be_purchased_and_renewed() -> None:
    email = f"custom-plan-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    code = f"ent{uuid.uuid4().hex[:6]}"
    try:
        async with SessionLocal() as db:
            db.add(
                Plan(
                    code=code,
                    name="Enterprise",
                    monthly_price=Decimal("9.99"),
                    max_stores=25,
                    max_members=50,
                    transaction_limit=500000,
                    description="Custom tier",
                    capabilities={"inventory_management": True},
                    is_active=True,
                )
            )
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await register_workspace(client, email, "free")
            company_id = workspace["company"]["id"]

            first = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": code, "billing_cycle": "monthly"})
            assert first.status_code == 201, first.text
            first_payment = first.json()["payment"]
            completed = await client.post(f"/api/v1/mock/chamabapay/{first_payment['external_id']}/complete")
            assert completed.status_code == 204, completed.text
            current = await client.get("/api/v1/billing/subscription", headers=headers)
            assert current.json()["plan_code"] == code
            assert current.json()["status"] == "active"

            # Early renewal of the same custom plan must be accepted too.
            second = await client.post("/api/v1/billing/checkout", headers=headers, json={"plan_code": code, "billing_cycle": "monthly"})
            assert second.status_code == 201, second.text
            second_payment = second.json()["payment"]
            completed = await client.post(f"/api/v1/mock/chamabapay/{second_payment['external_id']}/complete")
            assert completed.status_code == 204, completed.text

        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    text("SELECT status, plan_code FROM subscriptions WHERE company_id = :cid AND plan_code = :code ORDER BY starts_at"),
                    {"cid": company_id, "code": code},
                )
            ).mappings().all()
            assert len(rows) == 2
            assert all(row["status"] == "active" for row in rows)
    finally:
        await cleanup([email], company_id)
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM plans WHERE code = :code"), {"code": code})
            await db.commit()
