"""Phase 2: roles CRUD + custom role assignment."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


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


async def _owner(client, plan="pro"):
    email = f"p2-owner-{uuid.uuid4().hex[:10]}@example.com"
    reg = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "P2 Owner", "password": "strong-password"})
    assert reg.status_code == 201, reg.text
    await client.post("/api/v1/auth/verify-email", json={"token": reg.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post("/api/v1/workspaces/setup", headers=headers, json={"company_name": "P2 Co", "store_name": "Main", "currency_code": "USD", "plan_code": plan})
    assert setup.status_code == 201, setup.text
    ws = setup.json()
    if plan != "free":
        await client.post(f"/api/v1/mock/chamabapay/{ws['billing_payment']['external_id']}/complete")
    return headers, email, ws


@pytest.mark.asyncio
async def test_custom_role_crud_and_assignment() -> None:
    company_id = None
    emails: list[str] = []
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            owner, owner_email, ws = await _owner(client)
            emails.append(owner_email)
            company_id = ws["company"]["id"]
            store_id = ws["store"]["id"]

            catalog = await client.get("/api/v1/permissions", headers=owner)
            assert catalog.status_code == 200 and any(row["key"] == "sales.refund" for row in catalog.json())

            roles = await client.get("/api/v1/roles", headers=owner)
            assert roles.status_code == 200
            assert {row["key"] for row in roles.json()} == {"owner", "manager", "inventory_manager", "cashier"}

            created = await client.post("/api/v1/roles", headers=owner, json={"name": "Floor lead", "permissions": ["sales.create", "orders.view"]})
            assert created.status_code == 201, created.text
            custom = created.json()
            assert custom["is_system"] is False and custom["key"].startswith("role_")
            assert set(custom["permissions"]) == {"sales.create", "orders.view"}

            bad = await client.post("/api/v1/roles", headers=owner, json={"name": "Nope", "permissions": ["not.a.permission"]})
            assert bad.status_code == 400

            # Owner and built-in roles are protected.
            owner_role = next(row for row in roles.json() if row["key"] == "owner")
            assert (await client.patch(f"/api/v1/roles/{owner_role['id']}", headers=owner, json={"permissions": ["sales.create"]})).status_code == 400
            assert (await client.delete(f"/api/v1/roles/{owner_role['id']}", headers=owner)).status_code == 400

            # Assign the custom role via invitation and confirm resolution.
            member_email = f"p2-member-{uuid.uuid4().hex[:10]}@example.com"
            emails.append(member_email)
            invite = await client.post("/api/v1/team/invitations", headers=owner, json={"email": member_email, "role": custom["key"], "store_ids": [store_id]})
            assert invite.status_code == 201, invite.text
            accepted = await client.post("/api/v1/team/invitations/accept", json={"token": invite.json()["dev_invitation_token"], "full_name": "Floor Lead", "password": "strong-password"})
            assert accepted.status_code == 200, accepted.text
            member = {"Authorization": f"Bearer {accepted.json()['access_token']}"}
            member_ws = await client.get("/api/v1/workspaces/current", headers=member)
            assert member_ws.status_code == 200, member_ws.text
            assert set(member_ws.json()["permissions"]) == {"sales.create", "orders.view"}
    finally:
        await _cleanup(company_id, emails)


@pytest.mark.asyncio
async def test_custom_roles_require_the_plan_feature() -> None:
    company_id = None
    emails: list[str] = []
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            owner, owner_email, ws = await _owner(client, plan="free")
            emails.append(owner_email)
            company_id = ws["company"]["id"]
            blocked = await client.post("/api/v1/roles", headers=owner, json={"name": "Manager plus", "permissions": ["sales.create"]})
            assert blocked.status_code == 403, blocked.text
    finally:
        await _cleanup(company_id, emails)
