from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app

pytestmark = pytest.mark.asyncio


async def _cleanup(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                "DELETE FROM subscriptions WHERE company_id = :company_id",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM stock_movements USING stores WHERE stock_movements.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM inventory_balances USING stores WHERE inventory_balances.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM payments USING orders, stores WHERE payments.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM order_items USING orders, stores WHERE order_items.order_id = orders.id AND orders.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM orders USING stores WHERE orders.store_id = stores.id AND stores.company_id = :company_id",
                "DELETE FROM products WHERE company_id = :company_id",
                "DELETE FROM categories WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]
            for statement in statements:
                await db.execute(text(statement), parameters)
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


async def test_chamabapay_mock_billing_and_pos_flow() -> None:
    email = f"chamabapay-flow-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "ChmabaPay Owner", "password": "strong-password"})
            assert register.status_code == 201
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            setup = await client.post(
                "/api/v1/workspaces/setup",
                headers=headers,
                json={"company_name": "ChmabaPay Flow Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
            )
            assert setup.status_code == 201
            workspace = setup.json()
            company_id = workspace["company"]["id"]
            store_id = workspace["store"]["id"]
            store_headers = {**headers, "X-Store-ID": store_id}

            billing_payment = workspace["billing_payment"]
            assert billing_payment is not None
            assert billing_payment["provider"] == "chamabapay"

            completed = await client.post(f"/api/v1/mock/chamabapay/{billing_payment['external_id']}/complete", headers=headers)
            assert completed.status_code == 204
            subscription = await client.get("/api/v1/billing/subscription", headers=headers)
            assert subscription.status_code == 200
            assert subscription.json()["status"] == "active"

            linked = await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": "https://link.payway.com.kh/ABAPAYpe518710Y"})
            assert linked.status_code == 200
            assert linked.json()["aba_payway_status"] == "active"

            categories = await client.get("/api/v1/categories", headers=headers)
            assert categories.status_code == 200
            category_id = categories.json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "CP Latte", "sku": f"CP-{uuid.uuid4().hex[:8]}", "price": "4.50", "category_id": category_id, "opening_stock": 5, "reorder_point": 1},
            )
            assert product.status_code == 201
            product_id = product.json()["id"]

            khqr_order = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "khqr"})
            assert khqr_order.status_code == 201
            assert khqr_order.json()["status"] == "payment_pending"
            assert khqr_order.json()["payments"][0]["provider"] == "chamabapay"
            external_id = khqr_order.json()["payments"][0]["external_id"]

            done = await client.post(f"/api/v1/mock/chamabapay/{external_id}/complete")
            assert done.status_code == 204
            after = await client.get(f"/api/v1/orders/{khqr_order.json()['id']}", headers=store_headers)
            assert after.status_code == 200
            assert after.json()["status"] == "paid"
    finally:
        await _cleanup(email, company_id)
