"""Role -> endpoint enforcement matrix.

Pins the intended guard for the routes that shipped too permissive (see
docs/roles-permissions-audit.md and docs/roles-permissions-hardening-plan.md).
A regression in any of these guards fails here instead of silently exposing the
route to cashiers.

Roles: owner, manager, inventory_manager, cashier.
Guard groups: owner-only, owner+manager, catalog_roles (owner/manager/inventory).
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app

CLEANUP = [
    "DELETE FROM dining_tables WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
    "DELETE FROM dining_areas WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
    "DELETE FROM purchase_orders WHERE company_id = :company_id",
    "DELETE FROM suppliers WHERE company_id = :company_id",
    "DELETE FROM customers WHERE company_id = :company_id",
    "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
    "DELETE FROM subscriptions WHERE company_id = :company_id",
    "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
    "DELETE FROM memberships WHERE company_id = :company_id",
    "DELETE FROM invitations WHERE company_id = :company_id",
    "DELETE FROM company_currencies WHERE company_id = :company_id",
    "DELETE FROM notifications USING stores WHERE notifications.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM stock_movements USING stores WHERE stock_movements.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM inventory_balances USING stores WHERE inventory_balances.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM order_items USING orders, stores WHERE order_items.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM orders USING stores WHERE orders.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM products WHERE company_id = :company_id",
    "DELETE FROM categories WHERE company_id = :company_id",
    "DELETE FROM stores WHERE company_id = :company_id",
    "DELETE FROM companies WHERE id = :company_id",
]


async def cleanup(company_id, emails) -> None:
    if not company_id:
        return
    async with SessionLocal() as db:
        for statement in CLEANUP:
            await db.execute(text(statement), {"company_id": company_id})
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = ANY(:emails))"), {"emails": emails})
        await db.execute(text("DELETE FROM users WHERE email = ANY(:emails)"), {"emails": emails})
        await db.commit()


async def invite(client, owner_headers, email, role, store_id):
    invite_resp = await client.post("/api/v1/team/invitations", headers=owner_headers, json={"email": email, "role": role, "store_ids": [store_id]})
    assert invite_resp.status_code == 201, invite_resp.text
    accepted = await client.post("/api/v1/team/invitations/accept", json={"token": invite_resp.json()["dev_invitation_token"], "full_name": f"Matrix {role}", "password": "strong-password"})
    assert accepted.status_code == 200, accepted.text
    return {"Authorization": f"Bearer {accepted.json()['access_token']}"}


@pytest.mark.asyncio
async def test_role_endpoint_matrix() -> None:
    owner_email = f"matrix-owner-{uuid.uuid4().hex[:10]}@example.com"
    emails = [owner_email]
    company_id = None
    failures: list[str] = []
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            reg = await client.post("/api/v1/auth/register", json={"email": owner_email, "full_name": "Matrix Owner", "password": "strong-password"})
            assert reg.status_code == 201, reg.text
            await client.post("/api/v1/auth/verify-email", json={"token": reg.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": owner_email, "password": "strong-password"})
            owner = {"Authorization": f"Bearer {login.json()['access_token']}"}

            setup = await client.post("/api/v1/workspaces/setup", headers=owner, json={"company_name": "Matrix Co", "store_name": "Matrix Store", "currency_code": "USD", "plan_code": "pro"})
            assert setup.status_code == 201, setup.text
            ws = setup.json()
            company_id = ws["company"]["id"]
            store_id = ws["store"]["id"]
            await client.post(f"/api/v1/mock/chamabapay/{ws['billing_payment']['external_id']}/complete")

            categories = (await client.get("/api/v1/categories", headers=owner)).json()
            product = await client.post("/api/v1/products", headers={**owner, "X-Store-ID": store_id}, json={"name": "Matrix Widget", "sku": f"MX-{uuid.uuid4().hex[:8]}", "price": "4.00", "category_id": categories[0]["id"], "opening_stock": 20})
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]

            roles: dict[str, dict] = {"owner": owner}
            for role in ("manager", "inventory_manager", "cashier"):
                email = f"matrix-{role}-{uuid.uuid4().hex[:10]}@example.com"
                emails.append(email)
                roles[role] = await invite(client, owner, email, role, store_id)

            def h(role: str) -> dict:
                return {**roles[role], "X-Store-ID": store_id}

            # create a customer to target the loyalty adjustment
            cust = await client.post("/api/v1/customers", headers=h("owner"), json={"name": "Matrix Customer"})
            assert cust.status_code == 201, cust.text
            customer_id = cust.json()["id"]

            # (label, method, path, body, {role: expected_status})
            cases = [
                ("billing subscription", "GET", "/api/v1/billing/subscription", None, {"owner": 200, "manager": 403, "inventory_manager": 403, "cashier": 403}),
                ("billing payments", "GET", "/api/v1/billing/payments", None, {"owner": 200, "manager": 403, "inventory_manager": 403, "cashier": 403}),
                ("billing receipts", "GET", "/api/v1/billing/receipts", None, {"owner": 200, "manager": 403, "inventory_manager": 403, "cashier": 403}),
                ("team roster", "GET", "/api/v1/team", None, {"owner": 200, "manager": 403, "inventory_manager": 403, "cashier": 403}),
                ("send daily summary", "POST", "/api/v1/notifications/send-summary", None, {"owner": 200, "manager": 200, "inventory_manager": 403, "cashier": 403}),
                ("send low stock", "POST", "/api/v1/notifications/send-low-stock", None, {"owner": 200, "manager": 200, "inventory_manager": 403, "cashier": 403}),
                ("loyalty adjust", "PATCH", f"/api/v1/customers/{customer_id}/points", {"delta": 5}, {"owner": 200, "manager": 200, "inventory_manager": 403, "cashier": 403}),
                ("list suppliers", "GET", "/api/v1/suppliers", None, {"owner": 200, "manager": 200, "inventory_manager": 200, "cashier": 403}),
                ("create supplier", "POST", "/api/v1/suppliers", {"name": "Matrix Supplier"}, {"owner": 201, "manager": 201, "inventory_manager": 201, "cashier": 403}),
                ("list purchases", "GET", "/api/v1/purchases", None, {"owner": 200, "manager": 200, "inventory_manager": 200, "cashier": 403}),
                ("create purchase", "POST", "/api/v1/purchases", {"items": [{"product_id": product_id, "quantity": 1}]}, {"owner": 201, "manager": 201, "inventory_manager": 201, "cashier": 403}),
                ("create dining area", "POST", "/api/v1/dining/areas", lambda role: {"name": f"Matrix Area {role}", "position": 0}, {"owner": 201, "manager": 201, "inventory_manager": 403, "cashier": 403}),
            ]

            for label, method, path, body, expectations in cases:
                for role, expected in expectations.items():
                    payload = body(role) if callable(body) else body
                    response = await client.request(method, path, headers=h(role), json=payload) if payload is not None else await client.request(method, path, headers=h(role))
                    if response.status_code != expected:
                        failures.append(f"{label}: {role} expected {expected}, got {response.status_code}")
    finally:
        await cleanup(company_id, emails)
    assert not failures, "role matrix mismatches:\n" + "\n".join(failures)
