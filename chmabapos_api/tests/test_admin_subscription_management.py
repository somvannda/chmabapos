"""Platform support can grant, extend and revoke a plan without a payment."""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def _free_workspace(client: AsyncClient, email: str) -> dict:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Override Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Override Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json()


async def _promote_super(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("UPDATE users SET platform_role = 'super_admin' WHERE email = :email"), {"email": email})
        await db.commit()


async def _admin_headers(client: AsyncClient, email: str) -> dict:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _cleanup(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        if company_id:
            parameters = {"company_id": company_id}
            for statement in (
                "DELETE FROM audit_logs WHERE entity_id = :company_id",
                "DELETE FROM subscription_capacity_actions WHERE company_id = :company_id",
                "DELETE FROM billing_receipts WHERE company_id = :company_id",
                "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                "DELETE FROM subscriptions WHERE company_id = :company_id",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM categories WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ):
                await db.execute(text(statement), parameters)
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_super_admin_can_grant_extend_and_revoke_a_plan(monkeypatch) -> None:
    monkeypatch.setattr("app.api.v1.signature_is_valid", lambda *args, **kwargs: True)
    email = f"admin-sub-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace = await _free_workspace(client, email)
            company_id = workspace["company"]["id"]
        await _promote_super(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin = await _admin_headers(client, email)

            pending = await client.post("/api/v1/billing/checkout", headers=admin, json={"plan_code": "pro", "billing_cycle": "monthly"})
            assert pending.status_code == 201, pending.text
            pending_payment = pending.json()["payment"]

            plan = await client.post(
                f"/api/v1/admin/companies/{company_id}/subscription",
                headers=admin,
                json={"action": "grant", "plan_code": "starter", "billing_cycle": "annual", "reason": "support correction"},
            )
            assert plan.status_code == 200, plan.text
            body = plan.json()
            assert body["effective_plan_code"] == "starter"
            assert body["ends_at"] is not None

            # The superseded Pro checkout must not activate if its QR is paid late.
            late = {
                "id": f"evt_{uuid.uuid4().hex}",
                "type": "payment.test",
                "created": datetime.now().isoformat(),
                "data": {
                    "payment": {
                        "id": pending_payment["external_id"],
                        "status": "paid",
                        "amount": str(pending_payment["amount"]),
                        "currency": "USD",
                        "reference_id": pending_payment["reference_id"],
                    }
                },
            }
            assert (await client.post("/api/v1/webhooks/chamabapay", json=late)).status_code == 200
            still = await client.get(f"/api/v1/admin/companies/{company_id}/subscription", headers=admin)
            assert still.json()["effective_plan_code"] == "starter"

            current = await client.get(f"/api/v1/admin/companies/{company_id}/subscription", headers=admin)
            assert current.status_code == 200
            assert current.json()["effective_plan_code"] == "starter"

            before = datetime.fromisoformat(body["ends_at"].replace("Z", "+00:00"))
            extended = await client.post(
                f"/api/v1/admin/companies/{company_id}/subscription",
                headers=admin,
                json={"action": "extend", "days": 10, "reason": "goodwill"},
            )
            assert extended.status_code == 200, extended.text
            after = datetime.fromisoformat(extended.json()["ends_at"].replace("Z", "+00:00"))
            assert (after - before).days == 10

            revoked = await client.post(
                f"/api/v1/admin/companies/{company_id}/subscription",
                headers=admin,
                json={"action": "revoke", "reason": "chargeback"},
            )
            assert revoked.status_code == 200, revoked.text
            assert revoked.json()["effective_plan_code"] == "free"
            assert revoked.json()["ends_at"] is None

        async with SessionLocal() as db:
            actions = (
                await db.execute(text("SELECT action FROM audit_logs WHERE entity_id = :company_id ORDER BY created_at"), {"company_id": company_id})
            ).scalars().all()
            assert "admin.subscription_granted" in actions
            assert "admin.subscription_extended" in actions
            assert "admin.subscription_revoked" in actions
    finally:
        await _cleanup(email, company_id)
