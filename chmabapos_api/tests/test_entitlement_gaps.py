"""Free plans must not reach paid report or role-management surfaces."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_free_plan_cannot_read_advanced_reports() -> None:
    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Free Reports Co", "Main", plan="free")
            email, company_id = ctx["email"], ctx["company_id"]
            headers = ctx["store_headers"]
            for path in ("/api/v1/reports/margin", "/api/v1/reports/condition"):
                response = await client.get(path, headers=headers)
                assert response.status_code == 403, (path, response.text)
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_role_edit_requires_the_custom_roles_capability() -> None:
    """Custom roles are a Pro capability; Starter may only assign preset roles."""
    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Role Gate Co", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers = ctx["headers"]
            roles = await client.get("/api/v1/roles", headers=headers)
            manager = next(role for role in roles.json() if role["key"] == "manager")
            patched = await client.patch(
                f"/api/v1/roles/{manager['id']}",
                headers=headers,
                json={"permissions": ["sales.create"]},
            )
            assert patched.status_code == 403, patched.text
    finally:
        await cleanup_company(company_id, [email] if email else [])

@pytest.mark.asyncio
async def test_free_plan_cannot_take_table_orders() -> None:
    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Free Table Co", "Main", plan="free")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Table Latte", "sku": f"TB-{uuid.uuid4().hex[:8]}", "price": "4.00", "opening_stock": 5},
            )
            assert product.status_code == 201, product.text

            table_id = uuid.uuid4()
            token = uuid.uuid4().hex
            async with SessionLocal() as db:
                await db.execute(
                    text(
                        "INSERT INTO dining_tables (id, store_id, name, seats, status, qr_token, position, created_at, updated_at) "
                        "VALUES (:id, :store_id, 'T1', 2, 'available', :token, 0, now(), now())"
                    ),
                    {"id": table_id, "store_id": ctx["store_id"], "token": token},
                )
                await db.execute(
                    text("UPDATE stores SET public_order_enabled = true WHERE id = :store_id"),
                    {"store_id": ctx["store_id"]},
                )
                await db.commit()

            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product.json()["id"], "quantity": 1}],
                    "payment_method": "cash",
                    "table_id": str(table_id),
                    "order_type": "dine_in",
                },
            )
            assert order.status_code == 403, order.text

            workspace = (await client.get("/api/v1/workspaces/current", headers=headers)).json()
            public = await client.get(
                f"/api/v1/public/store/{workspace['company']['slug']}/{workspace['store']['slug']}",
                params={"table": token},
            )
            assert public.status_code == 404, public.text
    finally:
        await cleanup_company(company_id, [email] if email else [])
