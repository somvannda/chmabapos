"""A customer's lifetime total never adds two currencies together.

Bug B1 (docs/currency-policy.md §11.3): the customer detail summed Order.total
across every store in the company, so a KHR order's 4,000 was added to a USD total
as if it were dollars. The total must be converted to the company base, and the
response must say which currency it is in.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.models import ExchangeRate
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_total_spent_converts_a_khr_order_instead_of_adding_it_to_usd() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Total Co", "Main", plan="pro", email_prefix="total-currency")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_id = ctx["headers"], ctx["store_id"]

            # KHR must be enabled for the company before a store can price in it.
            currencies = await client.put(
                "/api/v1/settings/currencies", headers=headers, json={"primary_code": "USD", "enabled_codes": ["USD", "KHR"]}
            )
            assert currencies.status_code == 200, currencies.text

            # Price this store in riel, and drop tax so the maths is exactly the price.
            configured = await client.patch(
                f"/api/v1/stores/{store_id}", headers=headers, json={"currency_code": "KHR", "service_tax_rate": 0}
            )
            assert configured.status_code == 200, configured.text

            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={"name": "Riel Coffee", "sku": f"TC-{uuid.uuid4().hex[:8]}", "price": "4000", "category_id": category_id, "opening_stock": 5},
                )
            ).json()
            customer = (await client.post("/api/v1/customers", headers=headers, json={"name": "Riel Buyer"})).json()

            # One dollar buys 4,000 riel.
            async with SessionLocal() as db:
                user_id = await db.scalar(text("SELECT id FROM users WHERE email = :email"), {"email": email})
                db.add(
                    ExchangeRate(
                        company_id=uuid.UUID(str(company_id)),
                        base_currency_code="USD",
                        quote_currency_code="KHR",
                        rate=Decimal("4000"),
                        created_by=uuid.UUID(str(user_id)),
                    )
                )
                await db.commit()

            order = await client.post(
                "/api/v1/orders",
                headers=ctx["store_headers"],
                json={"items": [{"product_id": product["id"], "quantity": 1}], "payment_method": "cash", "customer_id": customer["id"]},
            )
            assert order.status_code == 201, order.text
            assert Decimal(order.json()["total"]) == Decimal("4000")

            detail = await client.get(f"/api/v1/customers/{customer['id']}", headers=headers)
            assert detail.status_code == 200, detail.text
            body = detail.json()
            # 4,000 riel is one dollar: the raw sum would have said 4000.
            assert body["total_spent"] == "1.00", body
            assert body["currency_code"] == "USD", body
            assert body["orders_count"] == 1
    finally:
        await cleanup_company(company_id, [email] if email else [])
