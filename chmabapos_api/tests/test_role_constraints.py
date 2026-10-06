"""Database-level role constraints reject unknown role strings.

The API validates roles with Pydantic, but the columns have no DB constraint, so
an out-of-band write could store a value that matches no guard. This pins the
CHECK constraints added in migration b8e4a2c1d3f5.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.main import app


async def cleanup(company_id, emails) -> None:
    async with SessionLocal() as db:
        if company_id is not None:
            for statement in [
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]:
                await db.execute(text(statement), {"company_id": company_id})
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = ANY(:emails))"), {"emails": emails})
        await db.execute(text("DELETE FROM users WHERE email = ANY(:emails)"), {"emails": emails})
        await db.commit()


@pytest.mark.asyncio
async def test_role_columns_reject_unknown_values() -> None:
    email = f"constraint-{uuid.uuid4().hex[:10]}@example.com"
    company_ref = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            reg = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Constraint", "password": "strong-password"})
            assert reg.status_code == 201, reg.text
            await client.post("/api/v1/auth/verify-email", json={"token": reg.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await client.post("/api/v1/workspaces/setup", headers=headers, json={"company_name": "Constraint Co", "store_name": "Main", "currency_code": "USD", "plan_code": "free"})
            assert setup.status_code == 201, setup.text
            company_ref = uuid.UUID(setup.json()["company"]["id"])

        async with SessionLocal() as db:
            # Membership roles are no longer a fixed DB enum (custom roles exist);
            # validity is enforced per company in the API.
            with pytest.raises(IntegrityError):
                await db.execute(text("UPDATE users SET platform_role = 'ghost' WHERE email = :email"), {"email": email})
                await db.commit()
            await db.rollback()

            # A valid role still updates, and the server default is in place.
            await db.execute(text("UPDATE memberships SET role = 'manager' WHERE company_id = :company_id"), {"company_id": company_ref})
            await db.commit()
            default = await db.scalar(text("SELECT column_default FROM information_schema.columns WHERE table_name = 'memberships' AND column_name = 'role'"))
            assert default and "cashier" in default
    finally:
        await cleanup(company_ref, [email])
