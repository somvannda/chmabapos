"""A QR that was already accepted must settle even if the quota filled later."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _set_starter_limit(limit: int) -> None:
    async with SessionLocal() as db:
        await db.execute(text("UPDATE plans SET transaction_limit = :limit WHERE code = 'starter'"), {"limit": limit})
        await db.commit()


async def _starter_limit() -> int:
    async with SessionLocal() as db:
        return int((await db.execute(text("SELECT transaction_limit FROM plans WHERE code = 'starter'"))).scalar_one())


@pytest.mark.asyncio
async def test_paid_qr_settles_after_the_limit_is_reached() -> None:
    # Restore whatever the plan ships with: a hardcoded old value silently
    # corrupts the plan row for every later test in the same database.
    original_limit = await _starter_limit()
    await _set_starter_limit(1)
    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Quota Settle Co", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            linked = await client.patch(
                "/api/v1/company",
                headers=headers,
                json={"aba_payway_link": "https://link.payway.com.kh/ABAPAYpe518710Y"},
            )
            assert linked.status_code == 200, linked.text

            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Settle Latte", "sku": f"QS-{uuid.uuid4().hex[:8]}", "price": "4.50", "opening_stock": 5},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]

            khqr = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "khqr"},
            )
            assert khqr.status_code == 201, khqr.text
            assert khqr.json()["status"] == "payment_pending"
            external_id = khqr.json()["payments"][0]["external_id"]

            # A cash sale fills the one-transaction limit while the QR is open.
            cash = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"},
            )
            assert cash.status_code == 201, cash.text

            settled = await client.post(f"/api/v1/mock/chamabapay/{external_id}/complete")
            assert settled.status_code == 204, settled.text
            after = await client.get(f"/api/v1/orders/{khqr.json()['id']}", headers=store_headers)
            assert after.status_code == 200
            assert after.json()["status"] == "paid"
    finally:
        await _set_starter_limit(original_limit)
        await cleanup_company(company_id, [email] if email else [])
