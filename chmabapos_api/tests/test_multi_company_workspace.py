"""Multi-company workspace resolution (audit §9.2 / design #540).

A user in more than one company must get a deterministic default (their owner
membership) and be able to switch, instead of being silently pinned to the
oldest membership.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def _workspace(client: AsyncClient, company_name: str, store_name: str) -> tuple[dict, str, str, str]:
    email = f"mc-{uuid.uuid4().hex[:10]}@example.com"
    reg = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Multi User", "password": "strong-password"})
    assert reg.status_code == 201, reg.text
    await client.post("/api/v1/auth/verify-email", json={"token": reg.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post("/api/v1/workspaces/setup", headers=headers, json={"company_name": company_name, "store_name": store_name, "currency_code": "USD", "plan_code": "free"})
    assert setup.status_code == 201, setup.text
    ws = setup.json()
    return headers, email, ws["company"]["id"], ws["store"]["id"]


async def _cleanup(company_ids, emails) -> None:
    async with SessionLocal() as db:
        for company_id in company_ids:
            for statement in [
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM invitations WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                "DELETE FROM subscriptions WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]:
                await db.execute(text(statement), {"company_id": uuid.UUID(str(company_id))})
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = ANY(:emails))"), {"emails": emails})
        await db.execute(text("DELETE FROM users WHERE email = ANY(:emails)"), {"emails": emails})
        await db.commit()


@pytest.mark.asyncio
async def test_multi_company_defaults_to_owner_and_can_switch() -> None:
    company_ids: list[str] = []
    emails: list[str] = []
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers_a, email_a, company_a, _store_a = await _workspace(client, "Company A", "A Store")
            _headers_b, email_b, company_b, store_b = await _workspace(client, "Company B", "B Store")
            company_ids = [company_a, company_b]
            emails = [email_a, email_b]

            # Add the first owner as a manager of company B.
            async with SessionLocal() as db:
                user_a = (await db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email_a})).scalar_one()
                membership_id = uuid.uuid4()
                await db.execute(text("INSERT INTO memberships (id, company_id, user_id, role, status, created_at) VALUES (:id, :company_id, :user_id, 'manager', 'active', now())"), {"id": membership_id, "company_id": uuid.UUID(company_b), "user_id": user_a})
                await db.execute(text("INSERT INTO membership_stores (membership_id, store_id) VALUES (:membership_id, :store_id)"), {"membership_id": membership_id, "store_id": uuid.UUID(store_b)})
                await db.commit()

            listed = await client.get("/api/v1/workspaces", headers=headers_a)
            assert listed.status_code == 200, listed.text
            assert {row["company_id"] for row in listed.json()} == {company_a, company_b}

            # No explicit choice yet -> the owner membership wins.
            current = await client.get("/api/v1/workspaces/current", headers=headers_a)
            assert current.status_code == 200, current.text
            assert current.json()["company"]["id"] == company_a

            switched = await client.post("/api/v1/workspaces/switch", headers=headers_a, json={"company_id": company_b})
            assert switched.status_code == 200, switched.text
            assert switched.json()["company"]["id"] == company_b
            assert switched.json()["membership_role"] == "manager"

            now = await client.get("/api/v1/workspaces/current", headers=headers_a)
            assert now.json()["company"]["id"] == company_b

            forbidden = await client.post("/api/v1/workspaces/switch", headers=headers_a, json={"company_id": str(uuid.uuid4())})
            assert forbidden.status_code == 404
    finally:
        await _cleanup(company_ids, emails)
