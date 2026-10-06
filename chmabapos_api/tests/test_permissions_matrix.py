"""Permission -> endpoint matrix for company custom roles.

A custom role with a domain permission reaches that domain's endpoints and is
denied elsewhere. Mirrors ``test_role_permissions_matrix.py`` for permissions.
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
                "DELETE FROM order_items USING orders, stores WHERE order_items.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM orders USING stores WHERE orders.store_id = stores.id AND stores.company_id = :company_id",
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


async def _member_with_permissions(client, owner, store_id, permissions, prefix):
    role = await client.post("/api/v1/roles", headers=owner, json={"name": f"{prefix} role", "permissions": permissions})
    assert role.status_code == 201, role.text
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    invite = await client.post("/api/v1/team/invitations", headers=owner, json={"email": email, "role": role.json()["key"], "store_ids": [store_id]})
    assert invite.status_code == 201, invite.text
    accepted = await client.post("/api/v1/team/invitations/accept", json={"token": invite.json()["dev_invitation_token"], "full_name": prefix, "password": "strong-password"})
    assert accepted.status_code == 200, accepted.text
    return {"Authorization": f"Bearer {accepted.json()['access_token']}", "X-Store-ID": store_id}, email


@pytest.mark.asyncio
async def test_custom_role_permission_matrix() -> None:
    company_id = None
    emails: list[str] = []
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            owner_email = f"pm-owner-{uuid.uuid4().hex[:10]}@example.com"
            emails.append(owner_email)
            reg = await client.post("/api/v1/auth/register", json={"email": owner_email, "full_name": "PM Owner", "password": "strong-password"})
            assert reg.status_code == 201, reg.text
            await client.post("/api/v1/auth/verify-email", json={"token": reg.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": owner_email, "password": "strong-password"})
            owner = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await client.post("/api/v1/workspaces/setup", headers=owner, json={"company_name": "PM Co", "store_name": "Main", "currency_code": "USD", "plan_code": "pro"})
            assert setup.status_code == 201, setup.text
            ws = setup.json()
            company_id = ws["company"]["id"]
            store_id = ws["store"]["id"]
            await client.post(f"/api/v1/mock/chamabapay/{ws['billing_payment']['external_id']}/complete")

            categories = (await client.get("/api/v1/categories", headers=owner)).json()
            product = await client.post("/api/v1/products", headers={**owner, "X-Store-ID": store_id}, json={"name": "PM Widget", "sku": f"PM-{uuid.uuid4().hex[:8]}", "price": "3.00", "category_id": categories[0]["id"], "opening_stock": 10})
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]

            def product_body(name):
                return {"name": name, "sku": f"PMN-{uuid.uuid4().hex[:8]}", "price": "3.00", "category_id": categories[0]["id"]}

            # (prefix, permissions, [(method, path, body, expected)])
            cases = [
                ("pm-sales", ["sales.create"], [
                    ("POST", "/api/v1/orders", {"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"}, 201),
                    ("POST", "/api/v1/products", product_body("sales no"), 403),
                    ("PATCH", "/api/v1/company", {"phone": "010"}, 403),
                ]),
                ("pm-catalog", ["catalog.manage"], [
                    ("POST", "/api/v1/products", product_body("catalog yes"), 201),
                    ("PATCH", "/api/v1/company", {"phone": "010"}, 403),
                ]),
                ("pm-settings", ["settings.manage"], [
                    ("PATCH", "/api/v1/company", {"phone": "010"}, 200),
                    ("POST", "/api/v1/products", product_body("settings no"), 403),
                ]),
                ("pm-team", ["team.manage"], [
                    ("POST", "/api/v1/roles", {"name": f"PM New {uuid.uuid4().hex[:6]}", "permissions": ["sales.create"]}, 201),
                    ("PATCH", "/api/v1/company", {"phone": "010"}, 403),
                ]),
            ]

            failures: list[str] = []
            for prefix, permissions, checks in cases:
                headers, email = await _member_with_permissions(client, owner, store_id, permissions, prefix)
                emails.append(email)
                for method, path, body, expected in checks:
                    response = await client.request(method, path, headers=headers, json=body)
                    if response.status_code != expected:
                        failures.append(f"{prefix} {method} {path}: expected {expected}, got {response.status_code}")
            assert not failures, "permission matrix mismatches:\n" + "\n".join(failures)
    finally:
        await _cleanup(company_id, emails)
