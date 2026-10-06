"""Phase 4: guards accept custom roles through their permissions.

A custom role with ``catalog.manage`` can manage the catalog; one without it,
and a built-in cashier, cannot. Built-in behavior is otherwise unchanged.
"""
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
                "DELETE FROM stock_movements USING stores WHERE stock_movements.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM inventory_balances USING stores WHERE inventory_balances.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM products WHERE company_id = :company_id",
                "DELETE FROM categories WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]:
                await db.execute(text(statement), {"company_id": uuid.UUID(str(company_id))})
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = ANY(:emails))"), {"emails": emails})
            await db.execute(text("DELETE FROM users WHERE email = ANY(:emails)"), {"emails": emails})
            await db.commit()


async def _register_and_login(client, prefix):
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    reg = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "P4", "password": "strong-password"})
    assert reg.status_code == 201, reg.text
    await client.post("/api/v1/auth/verify-email", json={"token": reg.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, email


async def _assign(client, owner, custom_key, store_id, prefix):
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    invite = await client.post("/api/v1/team/invitations", headers=owner, json={"email": email, "role": custom_key, "store_ids": [store_id]})
    assert invite.status_code == 201, invite.text
    accepted = await client.post("/api/v1/team/invitations/accept", json={"token": invite.json()["dev_invitation_token"], "full_name": "P4 member", "password": "strong-password"})
    assert accepted.status_code == 200, accepted.text
    return {"Authorization": f"Bearer {accepted.json()['access_token']}", "X-Store-ID": store_id}, email


@pytest.mark.asyncio
async def test_custom_role_reaches_catalog_through_permission() -> None:
    company_id = None
    emails: list[str] = []
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            owner, owner_email = await _register_and_login(client, "p4-owner")
            emails.append(owner_email)
            setup = await client.post("/api/v1/workspaces/setup", headers=owner, json={"company_name": "P4 Co", "store_name": "Main", "currency_code": "USD", "plan_code": "pro"})
            assert setup.status_code == 201, setup.text
            ws = setup.json()
            company_id = ws["company"]["id"]
            store_id = ws["store"]["id"]
            await client.post(f"/api/v1/mock/chamabapay/{ws['billing_payment']['external_id']}/complete")

            categories = (await client.get("/api/v1/categories", headers=owner)).json()
            category_id = categories[0]["id"]

            buyer = await client.post("/api/v1/roles", headers=owner, json={"name": "Buyer", "permissions": ["catalog.view", "catalog.manage"]})
            assert buyer.status_code == 201, buyer.text
            buyer_key = buyer.json()["key"]

            till = await client.post("/api/v1/roles", headers=owner, json={"name": "Till", "permissions": ["sales.create", "catalog.view"]})
            assert till.status_code == 201, till.text
            till_key = till.json()["key"]

            buyer_h, buyer_email = await _assign(client, owner, buyer_key, store_id, "p4-buyer")
            emails.append(buyer_email)
            till_h, till_email = await _assign(client, owner, till_key, store_id, "p4-till")
            emails.append(till_email)

            # A custom role with catalog.manage can create a product.
            made = await client.post("/api/v1/products", headers=buyer_h, json={"name": "P4 Widget", "sku": f"P4-{uuid.uuid4().hex[:8]}", "price": "3.00", "category_id": category_id, "opening_stock": 5})
            assert made.status_code == 201, made.text

            # A custom role without it is denied.
            denied = await client.post("/api/v1/products", headers=till_h, json={"name": "P4 Nope", "sku": f"P4N-{uuid.uuid4().hex[:8]}", "price": "3.00", "category_id": category_id})
            assert denied.status_code == 403, denied.text
    finally:
        await _cleanup(company_id, emails)
