"""Admin platform-wide sales and inventory analytics."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Sales Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Sales Analytics Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json(), headers


async def promote_to_admin(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": email})
        await db.commit()


async def login_headers(client: AsyncClient, email: str) -> dict:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def cleanup(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        await db.execute(
            text("DELETE FROM platform_activities WHERE company_id = :company_id OR user_id IN (SELECT id FROM users WHERE email = :email)"),
            {"company_id": company_id, "email": email},
        )
        await db.execute(text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM subscription_capacity_actions WHERE company_id = :company_id",
                "DELETE FROM billing_refunds WHERE company_id = :company_id",
                "DELETE FROM billing_receipts WHERE company_id = :company_id",
                "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                "DELETE FROM subscriptions WHERE company_id = :company_id",
                "DELETE FROM stock_movements WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM inventory_balances WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM variant_inventory_balances WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id))",
                "DELETE FROM orders WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM product_variants WHERE product_id IN (SELECT id FROM products WHERE company_id = :company_id)",
                "DELETE FROM products WHERE company_id = :company_id",
                "DELETE FROM customers WHERE company_id = :company_id",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM invitations WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM categories WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]
            for statement in statements:
                await db.execute(text(statement), parameters)
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_sales_analytics_requires_platform_admin() -> None:
    email = f"admin-sa-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            denied = await client.get("/api/v1/admin/sales-analytics", headers=headers)
            assert denied.status_code == 403
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_sales_analytics_shape_and_window() -> None:
    email = f"admin-sa-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            store_id = workspace["store"]["id"]
            product = await client.post(
                "/api/v1/products",
                headers={**headers, "X-Store-ID": store_id},
                json={"name": "Analytics Widget", "sku": f"AW-{uuid.uuid4().hex[:8]}", "price": "12.00", "cost_price": "5.00", "opening_stock": 4},
            )
            assert product.status_code == 201
        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)
            response = await client.get("/api/v1/admin/sales-analytics", headers=admin_headers, params={"days": 30})
            assert response.status_code == 200
            data = response.json()
            assert data["window_days"] == 30
            summary = data["summary"]
            for field in (
                "orders_total", "orders_window", "gmv_total", "gmv_window", "gmv_currency",
                "average_order_value", "refunds_window", "refund_count_window",
            ):
                assert field in summary, field
            assert summary["gmv_currency"]
            for key in ("top_companies", "top_stores", "top_products", "payment_methods"):
                assert isinstance(data[key], list)
            inventory = data["inventory"]
            for field in ("inventory_value", "low_stock_count", "out_of_stock_count", "active_products"):
                assert field in inventory, field
            assert inventory["active_products"] >= 1
            assert inventory["low_stock_count"] >= 0
            assert inventory["out_of_stock_count"] >= 0
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_sales_analytics_values_variant_stock_at_variant_cost() -> None:
    email = f"admin-sa-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            store_headers = {**headers, "X-Store-ID": workspace["store"]["id"]}
        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)
            before = (await client.get("/api/v1/admin/sales-analytics", headers=admin_headers, params={"days": 30})).json()["inventory"]["inventory_value"]

            # A variant product keeps its units on the variants and leaves the
            # product row at zero, so only a variant-aware figure sees this stock.
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Variant Widget", "sku": f"VW-{uuid.uuid4().hex[:8]}", "price": "20.00", "cost_price": "4.00"},
            )
            assert product.status_code == 201, product.text
            created = await client.put(
                f"/api/v1/products/{product.json()['id']}/variants",
                headers=store_headers,
                json={"variants": [{"sku": f"VW-A-{uuid.uuid4().hex[:6]}", "name": "Small", "price": "20.00", "cost_price": "6.00", "opening_stock": 2}]},
            )
            assert created.status_code == 200, created.text

            after = (await client.get("/api/v1/admin/sales-analytics", headers=admin_headers, params={"days": 30})).json()["inventory"]["inventory_value"]
            # 2 units at the variant's own cost, not the product's.
            assert Decimal(str(after)) - Decimal(str(before)) == Decimal("12.00")
    finally:
        await cleanup(email, company_id)
