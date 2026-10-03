from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


@pytest.mark.asyncio
async def test_setup_checklist_reflects_vertical_and_progress() -> None:
    email = f"checklist-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Checklist Owner", "password": "strong-password"})
            assert register.status_code == 201
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            setup = await client.post(
                "/api/v1/workspaces/setup",
                headers=headers,
                json={"company_name": "Checklist Electronics", "store_name": "Main", "currency_code": "USD", "plan_code": "free", "vertical": "electronics", "team_size_band": "2-10"},
            )
            assert setup.status_code == 201
            company_id = setup.json()["company"]["id"]

            res = await client.get("/api/v1/setup/checklist", headers=headers)
            assert res.status_code == 200
            body = res.json()
            assert body["total"] == 5
            assert body["completed"] == 0
            assert body["goal"] == "first_sale"
            assert body["next_step_id"] == "first-sale"
            # A first sale comes first so the owner sees the register work before
            # entering their own catalogue.
            first = body["steps"][0]
            assert first["id"] == "first-sale"
            assert first["done"] is False
            # Seeded sample products do not count as "added a product".
            add_product = next(step for step in body["steps"] if step["id"] == "add-product")
            # Wording adapts to the business type.
            assert add_product["title"] == "Add products with serial numbers"
            assert add_product["done"] is False
            assert add_product["article_id"] == "getting-started.add-products"

            # A brand-new workspace is seeded with sellable demo items, flagged
            # so they never count as the merchant's own catalogue.
            store_id = setup.json()["store"]["id"]
            products = await client.get("/api/v1/products", headers={**headers, "X-Store-ID": store_id}, params={"active_only": False})
            assert products.status_code == 200
            rows = products.json()
            assert rows, "a new workspace should be seeded with sample products"
            assert all(row["is_sample"] is True for row in rows)
            assert all(row["name"].startswith("Sample") for row in rows)

            # Removing the samples deletes untouched ones and empties the list.
            cleared = await client.post("/api/v1/workspace/sample-products/clear", headers=headers)
            assert cleared.status_code == 200
            cleared_body = cleared.json()
            assert cleared_body["deleted"] == len(rows)
            assert cleared_body["deactivated"] == 0
            after = await client.get("/api/v1/products", headers={**headers, "X-Store-ID": store_id}, params={"active_only": False})
            assert after.json() == []
    finally:
        async with SessionLocal() as db:
            if company_id:
                parameters = {"company_id": company_id}
                statements = [
                    "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id=memberships.id AND memberships.company_id=:company_id",
                    "DELETE FROM memberships WHERE company_id=:company_id",
                    "DELETE FROM company_currencies WHERE company_id=:company_id",
                    "DELETE FROM categories WHERE company_id=:company_id",
                    "DELETE FROM stores WHERE company_id=:company_id",
                    "DELETE FROM subscriptions WHERE company_id=:company_id",
                    "DELETE FROM companies WHERE id=:company_id",
                ]
                for statement in statements:
                    await db.execute(text(statement), parameters)
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email=:email)"), {"email": email})
            await db.execute(text("DELETE FROM users WHERE email=:email"), {"email": email})
            await db.commit()


@pytest.mark.asyncio
async def test_clear_sample_products_deactivates_sold_samples() -> None:
    email = f"sample-clear-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Sample Owner", "password": "strong-password"})
            assert register.status_code == 201
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await client.post(
                "/api/v1/workspaces/setup",
                headers=headers,
                json={"company_name": "Sample Clear Store", "store_name": "Main", "currency_code": "USD", "plan_code": "free", "vertical": "shop"},
            )
            assert setup.status_code == 201
            company_id = setup.json()["company"]["id"]
            store_id = setup.json()["store"]["id"]
            store_headers = {**headers, "X-Store-ID": store_id}
            samples = (await client.get("/api/v1/products", headers=store_headers, params={"active_only": False})).json()
            assert len(samples) >= 2
            sold = samples[0]
            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": sold["id"], "quantity": 1}], "payment_method": "cash"},
            )
            assert order.status_code == 201, order.text

            cleared = await client.post("/api/v1/workspace/sample-products/clear", headers=headers)
            assert cleared.status_code == 200
            body = cleared.json()
            # The sold sample is kept (deactivated); the rest are deleted.
            assert body["deactivated"] == 1
            assert body["deleted"] == len(samples) - 1

            remaining = (await client.get("/api/v1/products", headers=store_headers, params={"active_only": False})).json()
            sold_rows = [row for row in remaining if row["id"] == sold["id"]]
            assert len(sold_rows) == 1 and sold_rows[0]["is_active"] is False
    finally:
        async with SessionLocal() as db:
            if company_id:
                parameters = {"company_id": company_id}
                statements = [
                    "DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id=:company_id))",
                    "DELETE FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id=:company_id)",
                    "DELETE FROM notifications USING stores WHERE notifications.store_id = stores.id AND stores.company_id=:company_id",
                    "DELETE FROM stock_movements WHERE store_id IN (SELECT id FROM stores WHERE company_id=:company_id)",
                    "DELETE FROM inventory_balances WHERE store_id IN (SELECT id FROM stores WHERE company_id=:company_id)",
                    "DELETE FROM products WHERE company_id=:company_id",
                    "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id=memberships.id AND memberships.company_id=:company_id",
                    "DELETE FROM memberships WHERE company_id=:company_id",
                    "DELETE FROM company_currencies WHERE company_id=:company_id",
                    "DELETE FROM categories WHERE company_id=:company_id",
                    "DELETE FROM stores WHERE company_id=:company_id",
                    "DELETE FROM subscriptions WHERE company_id=:company_id",
                    "DELETE FROM companies WHERE id=:company_id",
                ]
                for statement in statements:
                    await db.execute(text(statement), parameters)
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email=:email)"), {"email": email})
            await db.execute(text("DELETE FROM users WHERE email=:email"), {"email": email})
            await db.commit()


@pytest.mark.asyncio
async def test_setup_checklist_adapts_to_onboarding_answers() -> None:
    email = f"checklist-bands-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Bands Owner", "password": "strong-password"})
            assert register.status_code == 201
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await client.post(
                "/api/v1/workspaces/setup",
                headers=headers,
                json={"company_name": "Bands Multi", "store_name": "Main", "currency_code": "USD", "plan_code": "free", "vertical": "general", "store_count_band": "2-5", "team_size_band": "1"},
            )
            assert setup.status_code == 201
            company_id = setup.json()["company"]["id"]

            body = (await client.get("/api/v1/setup/checklist", headers=headers)).json()
            ids = [step["id"] for step in body["steps"]]
            # A multi-store merchant sees the second-store step; a solo merchant is
            # not nudged to invite a team.
            assert "add-store" in ids
            assert "team" not in ids
            assert body["goal"] == "first_sale"
            assert body["next_step_id"] == "first-sale"
    finally:
        async with SessionLocal() as db:
            if company_id:
                parameters = {"company_id": company_id}
                statements = [
                    "DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id=:company_id))",
                    "DELETE FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id=:company_id)",
                    "DELETE FROM notifications USING stores WHERE notifications.store_id = stores.id AND stores.company_id=:company_id",
                    "DELETE FROM stock_movements WHERE store_id IN (SELECT id FROM stores WHERE company_id=:company_id)",
                    "DELETE FROM inventory_balances WHERE store_id IN (SELECT id FROM stores WHERE company_id=:company_id)",
                    "DELETE FROM products WHERE company_id=:company_id",
                    "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id=memberships.id AND memberships.company_id=:company_id",
                    "DELETE FROM memberships WHERE company_id=:company_id",
                    "DELETE FROM company_currencies WHERE company_id=:company_id",
                    "DELETE FROM categories WHERE company_id=:company_id",
                    "DELETE FROM stores WHERE company_id=:company_id",
                    "DELETE FROM subscriptions WHERE company_id=:company_id",
                    "DELETE FROM companies WHERE id=:company_id",
                ]
                for statement in statements:
                    await db.execute(text(statement), parameters)
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email=:email)"), {"email": email})
            await db.execute(text("DELETE FROM users WHERE email=:email"), {"email": email})
            await db.commit()
