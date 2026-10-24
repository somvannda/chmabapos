"""The customer billing page can read the same quota the gate enforces."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_usage_reports_the_enforced_window_and_count() -> None:
    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Usage Store", "Main", plan="free")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]

            before = await client.get("/api/v1/billing/usage", headers=headers)
            assert before.status_code == 200, before.text
            body = before.json()
            assert body["plan_code"] == "free"
            assert body["transactions_used"] == 0
            assert body["transaction_limit"] == 3000
            assert body["transactions_remaining"] == 3000
            # Free has no prepaid period, so the quota is a rolling calendar
            # month and the page can show when it next resets.
            period_end = datetime.fromisoformat(body["period_end"].replace("Z", "+00:00"))
            assert period_end > datetime.now(timezone.utc)
            assert period_end.day == 1
            assert (period_end.hour, period_end.minute, period_end.second) == (0, 0, 0)

            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Usage Latte", "sku": f"US-{uuid.uuid4().hex[:8]}", "price": "4.00", "opening_stock": 5},
            )
            assert product.status_code == 201, product.text
            sale = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product.json()["id"], "quantity": 1}], "payment_method": "cash"},
            )
            assert sale.status_code == 201, sale.text

            after = await client.get("/api/v1/billing/usage", headers=headers)
            assert after.status_code == 200
            body = after.json()
            assert body["transactions_used"] == 1
            assert body["transactions_remaining"] == 2999
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_paid_usage_reports_the_period_end() -> None:
    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Paid Usage Store", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            usage = await client.get("/api/v1/billing/usage", headers=ctx["headers"])
            assert usage.status_code == 200, usage.text
            body = usage.json()
            assert body["plan_code"] == "starter"
            assert body["transaction_limit"] == 15000
            assert body["period_end"] is not None
            assert body["billing_cycle"] == "monthly"
    finally:
        await cleanup_company(company_id, [email] if email else [])
