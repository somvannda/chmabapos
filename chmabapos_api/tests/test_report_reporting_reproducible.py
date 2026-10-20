"""A report must not be rewritten by a rate row edited after the sale.

The consolidated report converts every order into the company's base currency.
Before this fix it did that with the rate *table* at the order's date, so
backfilling a rate changed last month's revenue. The sale now carries its own
rate (`orders.company_base_rate`), and the report must prefer it.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.models import ExchangeRate
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _add_rate(company_id: str, user_email: str, quote: str, rate: str, effective_from: datetime) -> None:
    async with SessionLocal() as db:
        user_id = await db.scalar(text("SELECT id FROM users WHERE email = :email"), {"email": user_email})
        db.add(
            ExchangeRate(
                company_id=uuid.UUID(str(company_id)),
                base_currency_code="USD",
                quote_currency_code=quote,
                rate=Decimal(rate),
                effective_from=effective_from,
                created_by=uuid.UUID(str(user_id)),
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_a_backfilled_rate_does_not_change_a_past_report() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Report Co", "Main", plan="pro", email_prefix="report-currency")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_id = ctx["headers"], ctx["store_id"]

            currencies = await client.put(
                "/api/v1/settings/currencies", headers=headers, json={"primary_code": "USD", "enabled_codes": ["USD", "KHR"]}
            )
            assert currencies.status_code == 200, currencies.text
            configured = await client.patch(f"/api/v1/stores/{store_id}", headers=headers, json={"currency_code": "KHR", "service_tax_rate": 0})
            assert configured.status_code == 200, configured.text

            # One dollar buys 4,000 riel, in force long before the sale.
            await _add_rate(company_id, email, "KHR", "4000", datetime(2020, 1, 1, tzinfo=timezone.utc))

            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={"name": "Report Coffee", "sku": f"RP-{uuid.uuid4().hex[:8]}", "price": "4000", "category_id": category_id, "opening_stock": 5},
                )
            ).json()
            order = await client.post(
                "/api/v1/orders",
                headers=ctx["store_headers"],
                json={"items": [{"product_id": product["id"], "quantity": 1}], "payment_method": "cash"},
            )
            assert order.status_code == 201, order.text

            first = await client.get("/api/v1/reports/consolidated", headers=headers)
            assert first.status_code == 200, first.text
            assert first.json()["base_currency_code"] == "USD"
            assert first.json()["net_sales"] == "1.00", first.json()

            # Backfill a different rate, effective before the sale. The report must
            # not move: the sale was booked at 4,000, and that is what it must keep.
            await _add_rate(company_id, email, "KHR", "8000", datetime(2021, 1, 1, tzinfo=timezone.utc))

            second = await client.get("/api/v1/reports/consolidated", headers=headers)
            assert second.status_code == 200, second.text
            assert second.json()["net_sales"] == "1.00", f"backfilled rate rewrote the report: {second.json()}"
    finally:
        await cleanup_company(company_id, [email] if email else [])
