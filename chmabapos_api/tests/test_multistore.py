from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app

CLEANUP = [
    "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
    "DELETE FROM subscriptions WHERE company_id = :company_id",
    "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
    "DELETE FROM memberships WHERE company_id = :company_id",
    "DELETE FROM invitations WHERE company_id = :company_id",
    "DELETE FROM company_currencies WHERE company_id = :company_id",
    "DELETE FROM notifications USING stores WHERE notifications.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM stock_movements USING stores WHERE stock_movements.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM inventory_balances USING stores WHERE inventory_balances.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM payments USING orders, stores WHERE payments.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM order_items USING orders, stores WHERE order_items.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM order_tenders USING orders, stores WHERE order_tenders.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM refunds USING orders, stores WHERE refunds.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM orders USING stores WHERE orders.store_id = stores.id AND stores.company_id = :company_id",
    "DELETE FROM products WHERE company_id = :company_id",
    "DELETE FROM categories WHERE company_id = :company_id",
    "DELETE FROM stores WHERE company_id = :company_id",
    "DELETE FROM companies WHERE id = :company_id",
]


async def cleanup(company_id, email, owner_email):
    if company_id:
        async with SessionLocal() as db:
            parameters = {"company_id": company_id}
            for statement in CLEANUP:
                await db.execute(text(statement), parameters)
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": owner_email})
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": owner_email})
            await db.commit()


@pytest.mark.asyncio
async def test_multistore_lifecycle() -> None:
    owner_email = f"multi-owner-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": owner_email, "full_name": "Multi Owner", "password": "strong-password"})
            assert register.status_code == 201
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": owner_email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            setup = await client.post("/api/v1/workspaces/setup", headers=headers, json={"company_name": "Multi Store Co", "store_name": "Branch One", "currency_code": "USD", "plan_code": "pro"})
            assert setup.status_code == 201
            workspace = setup.json()
            company_id = workspace["company"]["id"]
            s1 = workspace["store"]["id"]
            assert workspace["subscription"]["status"] == "pending"
            plan_paid = await client.post(f"/api/v1/mock/cutluy/{workspace['billing_payment']['external_id']}/complete")
            assert plan_paid.status_code == 204

            # Paying for Pro should immediately allow adding stores
            second = await client.post("/api/v1/stores", headers=headers, json={"name": "Branch Two", "currency_code": "USD", "timezone": "Asia/Phnom_Penh"})
            assert second.status_code == 201, second.text
            s2 = second.json()["id"]
            assert len((await client.get("/api/v1/stores", headers=headers)).json()) == 2

            s1_headers = {**headers, "X-Store-ID": s1}
            s2_headers = {**headers, "X-Store-ID": s2}
            categories = (await client.get("/api/v1/categories", headers=headers)).json()
            product = await client.post(
                "/api/v1/products",
                headers=s1_headers,
                json={"name": "Transfer Latte", "sku": f"MS-{uuid.uuid4().hex[:8]}", "price": "3.00", "category_id": categories[0]["id"], "opening_stock": 10, "reorder_point": 2},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]
            assert product.json()["on_hand"] == 10

            transfer = await client.post("/api/v1/inventory/transfers", headers=s1_headers, json={"to_store_id": s2, "items": [{"product_id": product_id, "quantity": 4}], "note": "restock branch two"})
            assert transfer.status_code == 200, transfer.text
            reference = transfer.json()["reference"]
            assert reference.startswith("TRF-")

            inv1 = {item["product_id"]: item["on_hand"] for item in (await client.get("/api/v1/inventory", headers=s1_headers)).json()}
            inv2 = {item["product_id"]: item["on_hand"] for item in (await client.get("/api/v1/inventory", headers=s2_headers)).json()}
            assert inv1[product_id] == 6
            assert inv2[product_id] == 4

            over = await client.post("/api/v1/inventory/transfers", headers=s1_headers, json={"to_store_id": s2, "items": [{"product_id": product_id, "quantity": 999}]})
            assert over.status_code == 409

            # Same-store transfer must be rejected
            same = await client.post("/api/v1/inventory/transfers", headers=s1_headers, json={"to_store_id": s1, "items": [{"product_id": product_id, "quantity": 1}]})
            assert same.status_code == 400

            # A paid sale at the second store feeds the consolidated report
            sale = await client.post("/api/v1/orders", headers=s2_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"})
            assert sale.status_code == 201, sale.text
            consolidated = await client.get("/api/v1/reports/consolidated", headers=headers)
            assert consolidated.status_code == 200, consolidated.text
            body = consolidated.json()
            assert body["stores_count"] == 2
            assert body["transactions"] >= 1
            assert body["per_store"][0]["store_id"] != body["per_store"][1]["store_id"]
            assert sum(float(store["net_sales"]) for store in body["per_store"]) == pytest.approx(float(body["net_sales"]), abs=0.01)

            # Consolidated report reports in the company base currency and lists transactions per store
            assert body["base_currency_code"] == "USD"
            assert len(body["transactions_detail"]) >= 1
            assert all(tx["store_name"] and tx["store_id"] and float(tx["total"]) > 0 for tx in body["transactions_detail"])
            assert all("refunds" in store and "refunds_count" in store and "average_order" in store for store in body["per_store"])

            # store_ids filters the report to the requested stores
            scoped = await client.get("/api/v1/reports/consolidated", headers=headers, params=[("store_ids", s1)])
            assert scoped.status_code == 200, scoped.text
            scoped_body = scoped.json()
            assert scoped_body["stores_count"] == 1
            assert [store["store_id"] for store in scoped_body["per_store"]] == [s1]
            assert scoped_body["transactions"] == 0

            scoped_both = await client.get("/api/v1/reports/consolidated", headers=headers, params=[("store_ids", s1), ("store_ids", s2)])
            assert scoped_both.status_code == 200, scoped_both.text
            assert scoped_both.json()["stores_count"] == 2

            unknown = uuid.uuid4()
            bad_scope = await client.get("/api/v1/reports/consolidated", headers=headers, params=[("store_ids", s1), ("store_ids", str(unknown))])
            assert bad_scope.status_code == 400

            # Non-owner cannot view the consolidated report
            cashier_email = f"multi-cashier-{uuid.uuid4().hex[:10]}@example.com"
            invite = await client.post("/api/v1/team/invitations", headers=headers, json={"email": cashier_email, "role": "cashier", "store_ids": [s1]})
            assert invite.status_code == 201, invite.text
            accepted = await client.post("/api/v1/team/invitations/accept", json={"token": invite.json()["dev_invitation_token"], "full_name": "Branch Cashier", "password": "strong-password"})
            assert accepted.status_code == 200
            cashier_headers = {"Authorization": f"Bearer {accepted.json()['access_token']}"}
            blocked = await client.get("/api/v1/reports/consolidated", headers=cashier_headers)
            assert blocked.status_code == 403

            # Soft-deactivate the second store then reactivate it
            deactivate = await client.patch(f"/api/v1/stores/{s2}", headers=headers, json={"is_active": False})
            assert deactivate.status_code == 200, deactivate.text
            assert [store["id"] for store in (await client.get("/api/v1/stores", headers=headers)).json()] == [s1]
            with_inactive = (await client.get("/api/v1/stores?include_inactive=true", headers=headers)).json()
            assert len(with_inactive) == 2
            assert next(store for store in with_inactive if store["id"] == s2)["is_active"] is False
            # Operations on the inactive store are blocked
            stale = await client.get("/api/v1/inventory", headers={**headers, "X-Store-ID": s2})
            assert stale.status_code == 404
            reactivate = await client.patch(f"/api/v1/stores/{s2}", headers=headers, json={"is_active": True})
            assert reactivate.status_code == 200
            assert len((await client.get("/api/v1/stores", headers=headers)).json()) == 2

            # Cannot deactivate the last active store
            off_one = await client.patch(f"/api/v1/stores/{s1}", headers=headers, json={"is_active": False})
            assert off_one.status_code == 200
            last = await client.patch(f"/api/v1/stores/{s2}", headers=headers, json={"is_active": False})
            assert last.status_code == 400
            await client.patch(f"/api/v1/stores/{s1}", headers=headers, json={"is_active": True})
    finally:
        await cleanup(company_id, owner_email, owner_email)
