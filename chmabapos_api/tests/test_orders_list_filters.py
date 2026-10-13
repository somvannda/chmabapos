from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_orders_list_filters_and_summary() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Orders Filter Store", "Main Counter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Filter Widget", "sku": f"OF-{uuid.uuid4().hex[:8]}", "price": "10.00", "category_id": category_id, "opening_stock": 50},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]

            customer = await client.post("/api/v1/customers", headers=headers, json={"name": "Dara Filter", "phone": "+85510000099"})
            assert customer.status_code == 201, customer.text
            customer_id = customer.json()["id"]

            takeaway = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash", "customer_id": customer_id},
            )
            assert takeaway.status_code == 201, takeaway.text
            order_number = takeaway.json()["order_number"]

            dine = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 2}], "payment_method": "cash", "order_type": "dine_in"},
            )
            assert dine.status_code == 201, dine.text

            # order_type narrows the list to dine-in only.
            only_dine = await client.get("/api/v1/orders", headers=store_headers, params={"order_type": "dine_in"})
            assert only_dine.status_code == 200, only_dine.text
            assert [row["order_type"] for row in only_dine.json()] == ["dine_in"]

            # search matches the order number.
            by_number = await client.get("/api/v1/orders", headers=store_headers, params={"search": order_number})
            assert by_number.status_code == 200, by_number.text
            assert [row["order_number"] for row in by_number.json()] == [order_number]

            # search matches the attached customer's name.
            by_customer = await client.get("/api/v1/orders", headers=store_headers, params={"search": "Dara Filter"})
            assert by_customer.status_code == 200, by_customer.text
            assert len(by_customer.json()) == 1

            # a date window covering today includes both orders; a past window excludes them.
            today = date.today().isoformat()
            in_window = await client.get("/api/v1/orders", headers=store_headers, params={"from_date": today, "to_date": today})
            assert in_window.status_code == 200, in_window.text
            assert len(in_window.json()) == 2
            past = await client.get("/api/v1/orders", headers=store_headers, params={"from_date": "2000-01-01", "to_date": "2000-01-02"})
            assert past.status_code == 200, past.text
            assert past.json() == []

            # summary reflects the same period.
            summary = await client.get("/api/v1/orders/summary", headers=store_headers)
            assert summary.status_code == 200, summary.text
            body = summary.json()
            assert body["orders_count"] == 2
            assert body["paid_count"] == 2
            assert body["pending_pickup_count"] == 0
            assert float(body["gross_total"]) == float(takeaway.json()["total"]) + float(dine.json()["total"])
            assert float(body["open_balance"]) == 0.0
    finally:
        await cleanup_company(company_id, [email] if email else [])
