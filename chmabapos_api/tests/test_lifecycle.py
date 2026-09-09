from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app

FREE = "free"


async def register_and_setup(client: AsyncClient, company_name: str, store_name: str, plan: str = FREE, email_prefix: str = "life") -> dict:
    email = f"{email_prefix}-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Lifecycle Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    setup = await client.post("/api/v1/workspaces/setup", headers=headers, json={"company_name": company_name, "store_name": store_name, "currency_code": "USD", "plan_code": plan})
    assert setup.status_code == 201, setup.text
    workspace = setup.json()
    if plan != "free":
        billing_id = workspace["billing_payment"]["external_id"]
        assert (await client.post(f"/api/v1/mock/cutluy/{billing_id}/complete")).status_code == 204
    store_headers = {**headers, "X-Store-ID": workspace["store"]["id"]}
    return {"email": email, "headers": headers, "store_headers": store_headers, "company_id": workspace["company"]["id"], "store_id": workspace["store"]["id"]}


async def cleanup_company(company_id: str, emails: list[str]) -> None:
    async with SessionLocal() as db:
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                "DELETE FROM subscriptions WHERE company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM membership_stores WHERE membership_id IN (SELECT id FROM memberships WHERE company_id = :company_id)",
                "DELETE FROM invitations WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM stock_movements USING stores WHERE stock_movements.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM inventory_balances USING stores WHERE inventory_balances.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM payments USING orders, stores WHERE payments.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM order_items USING orders, stores WHERE order_items.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM refunds USING orders, stores WHERE refunds.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM orders USING stores WHERE orders.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM held_orders USING stores WHERE held_orders.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM shifts USING stores WHERE shifts.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM products WHERE company_id = :company_id",
                "DELETE FROM categories WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]
            for statement in statements:
                await db.execute(text(statement), parameters)
        if emails:
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = ANY(:emails))"), {"emails": emails})
            await db.execute(text("DELETE FROM users WHERE email = ANY(:emails)"), {"emails": emails})
        await db.commit()


@pytest.mark.asyncio
async def test_customers_held_restock_refund_tax_shifts_and_pagination() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Lifecycle Store", "Main Counter", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]

            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Life Latte", "sku": f"LC-{uuid.uuid4().hex[:8]}", "price": "4.50", "category_id": category_id, "opening_stock": 40, "reorder_point": 2},
            )
            assert product.status_code == 201
            product_id = product.json()["id"]

            # ---- customers ----
            customer = await client.post("/api/v1/customers", headers=headers, json={"name": "Chan Meas", "phone": "+855 10 000 111", "email": "chan@example.com"})
            assert customer.status_code == 201
            customer_id = customer.json()["id"]
            assert (await client.get("/api/v1/customers?search=chan@example.com", headers=headers)).json()[0]["id"] == customer_id
            assert (await client.get("/api/v1/customers?search=10 000", headers=headers)).json()[0]["id"] == customer_id
            patched = await client.patch(f"/api/v1/customers/{customer_id}", headers=headers, json={"notes": "regular"})
            assert patched.status_code == 200 and patched.json()["notes"] == "regular"
            detail = await client.get(f"/api/v1/customers/{customer_id}", headers=headers)
            assert detail.json()["orders_count"] == 0

            # ---- held orders ----
            held = await client.post("/api/v1/held-orders", headers=store_headers, json={"label": "Table 2", "items": [{"product_id": product_id, "quantity": 2}]})
            assert held.status_code == 201, held.text
            assert held.json()["item_count"] == 2 and held.json()["total"] == "9.90"
            held_list = await client.get("/api/v1/held-orders", headers=store_headers)
            assert len(held_list.json()) == 1
            assert (await client.delete(f"/api/v1/held-orders/{held.json()['id']}", headers=store_headers)).status_code == 200

            # ---- restock ----
            restocked = await client.post(f"/api/v1/inventory/{product_id}/restock", headers=store_headers, json={"quantity": 20, "supplier": "Beans Co", "reference": "PO-1"})
            assert restocked.status_code == 200
            assert restocked.json()["on_hand"] == 60

            # ---- refunds ----
            sale = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 2}], "payment_method": "cash"})
            assert sale.status_code == 201 and sale.json()["status"] == "paid"
            order_id = sale.json()["id"]
            partial = await client.post(f"/api/v1/orders/{order_id}/refund", headers=store_headers, json={"method": "cash", "items": [{"product_id": product_id, "quantity": 1}]})
            assert partial.status_code == 201
            order_after = await client.get(f"/api/v1/orders/{order_id}", headers=store_headers)
            assert order_after.json()["status"] == "paid" and order_after.json()["refunded_amount"] == "4.95"
            assert len((await client.get(f"/api/v1/orders/{order_id}/refunds", headers=store_headers)).json()) == 1
            full = await client.post(f"/api/v1/orders/{order_id}/refund", headers=store_headers, json={"method": "cash", "items": [{"product_id": product_id, "quantity": 1}]})
            assert full.status_code == 201
            assert (await client.get(f"/api/v1/orders/{order_id}", headers=store_headers)).json()["status"] == "refunded"
            assert (await client.post(f"/api/v1/orders/{order_id}/refund", headers=store_headers, json={"method": "cash", "items": [{"product_id": product_id, "quantity": 1}]})).status_code == 409

            # ---- discount + configurable tax ----
            assert (await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"service_tax_rate": 5})).json()["service_tax_rate"] == "5.00"
            taxed = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"})
            assert taxed.json()["tax"] == "0.23" and taxed.json()["total"] == "4.73"
            discounted = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash", "discount": 1.00})
            assert discounted.json()["tax"] == "0.18" and discounted.json()["total"] == "3.68"
            await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"service_tax_rate": 10})

            # ---- email receipt ----
            attached = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "customer_id": customer_id, "payment_method": "cash"})
            assert attached.status_code == 201 and attached.json()["customer"]["email"] == "chan@example.com"
            emailed = await client.post(f"/api/v1/orders/{attached.json()['id']}/email-receipt", headers=store_headers)
            assert emailed.status_code == 200 and emailed.json()["email"] == "chan@example.com"
            assert (await client.get(f"/api/v1/customers/{customer_id}", headers=headers)).json()["orders_count"] >= 1

            # ---- shifts ----
            opened = await client.post("/api/v1/shifts/open", headers=store_headers, json={"opening_float": 25})
            assert opened.status_code == 201
            shift_id = opened.json()["id"]
            assert (await client.get("/api/v1/shifts/open", headers=store_headers)).json()["id"] == shift_id
            assert (await client.post("/api/v1/shifts/open", headers=store_headers, json={"opening_float": 10})).status_code == 409
            shift_sale = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"})
            assert shift_sale.json()["status"] == "paid"
            closed = await client.post(f"/api/v1/shifts/{shift_id}/close", headers=store_headers, json={"counted_cash": 29.95})
            assert closed.status_code == 200
            body = closed.json()
            assert body["cash_received"] == "4.95" and body["expected_cash"] == "29.95" and body["difference"] == "0.00" and body["orders_count"] == 1
            assert (await client.post(f"/api/v1/shifts/{shift_id}/close", headers=store_headers, json={"counted_cash": 1})).status_code == 409
            assert len((await client.get("/api/v1/shifts", headers=store_headers)).json()) == 1

            # ---- pagination offset ----
            page_a = (await client.get("/api/v1/orders?limit=2&offset=0", headers=store_headers)).json()
            page_b = (await client.get("/api/v1/orders?limit=2&offset=2", headers=store_headers)).json()
            assert len(page_a) == 2 and len(page_b) == 2
            assert {order["id"] for order in page_a}.isdisjoint({order["id"] for order in page_b})
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_cashier_cannot_refund_or_cancel_but_owner_can() -> None:
    emails: list[str] = []
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Role Store", "Role Counter", email_prefix="role", plan="starter")
            emails.append(ctx["email"])
            company_id = ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]

            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post("/api/v1/products", headers=store_headers, json={"name": "Role Cup", "sku": f"RC-{uuid.uuid4().hex[:8]}", "price": "3.00", "category_id": category_id, "opening_stock": 20, "reorder_point": 1})
            product_id = product.json()["id"]

            paid = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"})
            assert paid.status_code == 201
            async with SessionLocal() as db:
                await db.execute(text("UPDATE companies SET aba_payway_link = 'https://payway.example.com/role-test', aba_payway_status = 'active' WHERE id = :company_id"), {"company_id": company_id})
                await db.commit()
            pending = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "khqr"})
            assert pending.status_code == 201 and pending.json()["status"] == "payment_pending"

            teammate_email = f"cashier-{uuid.uuid4().hex[:10]}@example.com"
            emails.append(teammate_email)
            invite = await client.post("/api/v1/team/invitations", headers=headers, json={"email": teammate_email, "role": "cashier", "store_ids": [ctx["store_id"]]})
            token = invite.json()["dev_invitation_token"]
            accepted = await client.post("/api/v1/team/invitations/accept", json={"token": token, "full_name": "Role Cashier", "password": "strong-password"})
            assert accepted.status_code == 200
            cashier_login = await client.post("/api/v1/auth/login", json={"email": teammate_email, "password": "strong-password"})
            cashier_headers = {"Authorization": f"Bearer {cashier_login.json()['access_token']}", "X-Store-ID": ctx["store_id"]}

            denied_refund = await client.post(f"/api/v1/orders/{paid.json()['id']}/refund", headers=cashier_headers, json={"method": "cash", "items": [{"product_id": product_id, "quantity": 1}]})
            assert denied_refund.status_code == 403
            denied_cancel = await client.post(f"/api/v1/orders/{pending.json()['id']}/cancel", headers=cashier_headers)
            assert denied_cancel.status_code == 403

            ok_cancel = await client.post(f"/api/v1/orders/{pending.json()['id']}/cancel", headers=store_headers)
            assert ok_cancel.status_code == 200 and ok_cancel.json()["status"] == "cancelled"
            ok_refund = await client.post(f"/api/v1/orders/{paid.json()['id']}/refund", headers=store_headers, json={"method": "cash", "items": [{"product_id": product_id, "quantity": 1}]})
            assert ok_refund.status_code == 201
            assert (await client.get(f"/api/v1/orders/{paid.json()['id']}", headers=store_headers)).json()["status"] == "refunded"
    finally:
        await cleanup_company(company_id, emails)
