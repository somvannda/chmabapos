"""Archiving a plan must not strand the subscribers already on it."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _set_plan_active(active: bool) -> None:
    async with SessionLocal() as db:
        await db.execute(text("UPDATE plans SET is_active = :active WHERE code = 'starter'"), {"active": active})
        await db.commit()


@pytest.mark.asyncio
async def test_subscriber_can_renew_an_archived_plan_but_free_cannot_buy_it() -> None:
    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Archived Renewal Co", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers = ctx["headers"]

            await _set_plan_active(False)
            renewal = await client.post(
                "/api/v1/billing/checkout",
                headers=headers,
                json={"plan_code": "starter", "billing_cycle": "monthly"},
            )
            assert renewal.status_code == 201, renewal.text
            completed = await client.post(f"/api/v1/mock/chamabapay/{renewal.json()['payment']['external_id']}/complete")
            assert completed.status_code == 204, completed.text

            free_ctx = await register_and_setup(client, "Free Archived Buyer", "Main", plan="free")
            free_company = free_ctx["company_id"]
            try:
                denied = await client.post(
                    "/api/v1/billing/checkout",
                    headers=free_ctx["headers"],
                    json={"plan_code": "starter", "billing_cycle": "monthly"},
                )
                assert denied.status_code == 400, denied.text
                assert "Plan not found" in denied.text
            finally:
                await cleanup_company(free_company, [free_ctx["email"]])
    finally:
        await _set_plan_active(True)
        await cleanup_company(company_id, [email] if email else [])
