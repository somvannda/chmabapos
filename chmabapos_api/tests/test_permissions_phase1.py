"""Phase 1 of the permissions system: roles seeded, permissions resolved.

Behavior-preserving: ``Membership.role`` stays a string key, the built-in roles
are seeded per company, and the workspace payload exposes the resolved
permission set.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import Role
from app.permissions import ALL_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS


async def _cleanup(company_id, emails) -> None:
    if company_id is not None:
        async with SessionLocal() as db:
            for statement in [
                "DELETE FROM role_permissions USING roles WHERE role_permissions.role_id = roles.id AND roles.company_id = :company_id",
                "DELETE FROM roles WHERE company_id = :company_id",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM invitations WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]:
                await db.execute(text(statement), {"company_id": uuid.UUID(str(company_id))})
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = ANY(:emails))"), {"emails": emails})
            await db.execute(text("DELETE FROM users WHERE email = ANY(:emails)"), {"emails": emails})
            await db.commit()


@pytest.mark.asyncio
async def test_permissions_phase1_seeds_roles_and_resolves() -> None:
    owner_email = f"perm-owner-{uuid.uuid4().hex[:10]}@example.com"
    cashier_email = f"perm-cashier-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            reg = await client.post("/api/v1/auth/register", json={"email": owner_email, "full_name": "Perm Owner", "password": "strong-password"})
            assert reg.status_code == 201, reg.text
            await client.post("/api/v1/auth/verify-email", json={"token": reg.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": owner_email, "password": "strong-password"})
            owner = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await client.post("/api/v1/workspaces/setup", headers=owner, json={"company_name": "Perm Co", "store_name": "Main", "currency_code": "USD", "plan_code": "pro"})
            assert setup.status_code == 201, setup.text
            ws = setup.json()
            company_id = ws["company"]["id"]
            store_id = ws["store"]["id"]
            await client.post(f"/api/v1/mock/chamabapay/{ws['billing_payment']['external_id']}/complete")

            current = await client.get("/api/v1/workspaces/current", headers=owner)
            assert current.status_code == 200, current.text
            assert set(current.json()["permissions"]) == set(ALL_PERMISSIONS)

            invite = await client.post("/api/v1/team/invitations", headers=owner, json={"email": cashier_email, "role": "cashier", "store_ids": [store_id]})
            assert invite.status_code == 201, invite.text
            accepted = await client.post("/api/v1/team/invitations/accept", json={"token": invite.json()["dev_invitation_token"], "full_name": "Perm Cashier", "password": "strong-password"})
            assert accepted.status_code == 200, accepted.text
            cashier = {"Authorization": f"Bearer {accepted.json()['access_token']}"}

            cashier_ws = await client.get("/api/v1/workspaces/current", headers=cashier)
            assert cashier_ws.status_code == 200, cashier_ws.text
            assert set(cashier_ws.json()["permissions"]) == set(DEFAULT_ROLE_PERMISSIONS["cashier"])

        async with SessionLocal() as db:
            roles = (await db.execute(select(Role).where(Role.company_id == uuid.UUID(company_id)))).scalars().all()
            assert {role.key for role in roles} == {"owner", "manager", "inventory_manager", "cashier"}
            assert all(role.is_system for role in roles)
    finally:
        await _cleanup(company_id, [owner_email, cashier_email])
