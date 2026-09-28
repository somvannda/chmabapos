"""The public marketing stats endpoint is unauthenticated and reflects live data."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def _cleanup(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM stock_movements WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM inventory_balances WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id))",
                "DELETE FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM product_variants WHERE product_id IN (SELECT id FROM products WHERE company_id = :company_id)",
                "DELETE FROM products WHERE company_id = :company_id",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]
            for statement in statements:
                await db.execute(text(statement), parameters)
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_public_stats_is_unauthenticated_and_counts_new_data() -> None:
    email = f"public-stats-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            before_response = await client.get("/api/v1/public/stats")
            assert before_response.status_code == 200
            assert before_response.headers.get("cache-control") == "public, max-age=300"
            before = before_response.json()
            assert set(before) == {"active_stores", "completed_sales", "value_processed", "currency_code", "active_products"}
            assert isinstance(before["active_stores"], int)
            assert before["active_products"] >= 0
            assert before["currency_code"]

            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Stats Owner", "password": "strong-password"})
            assert register.status_code == 201
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await client.post(
                "/api/v1/workspaces/setup",
                headers=headers,
                json={"company_name": "Stats Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
            )
            assert setup.status_code == 201
            company_id = setup.json()["company"]["id"]
            store_headers = {**headers, "X-Store-ID": setup.json()["store"]["id"]}
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Stats Latte", "sku": f"STAT-{uuid.uuid4().hex[:8]}", "price": "4.50", "opening_stock": 5},
            )
            assert product.status_code == 201

            after = (await client.get("/api/v1/public/stats")).json()
            assert after["active_stores"] == before["active_stores"] + 1
            assert after["active_products"] == before["active_products"] + 1
            assert after["completed_sales"] >= before["completed_sales"]
    finally:
        await _cleanup(email, company_id)
