from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_batches_are_consumed_first_expiry_first_out() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "FEFO Store", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = await client.post(
                "/api/v1/products",
                headers=store_headers,
                json={"name": "Yogurt", "sku": f"FEFO-{uuid.uuid4().hex[:8]}", "price": "5.00", "category_id": category_id, "opening_stock": 20},
            )
            assert product.status_code == 201, product.text
            product_id = product.json()["id"]

            batches = await client.post(
                f"/api/v1/products/{product_id}/batches",
                headers=store_headers,
                json={"batches": [
                    {"batch_code": "LATE", "expiry_date": "2026-12-31", "quantity_on_hand": 5},
                    {"batch_code": "EARLY", "expiry_date": "2026-01-01", "quantity_on_hand": 3},
                    {"batch_code": "NONE", "quantity_on_hand": 2},
                ]},
            )
            assert batches.status_code == 201, batches.text

            # Sell 4: the earliest-expiry batch (3) is consumed first, then the
            # next one takes the remaining unit; the undated batch is untouched.
            sale = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 4}], "payment_method": "cash"})
            assert sale.status_code == 201, sale.text

            remaining = {row["batch_code"]: row["quantity_on_hand"] for row in (await client.get(f"/api/v1/products/{product_id}/batches", headers=store_headers)).json()}
            assert remaining["EARLY"] == 0
            assert remaining["LATE"] == 4
            assert remaining["NONE"] == 2
    finally:
        await cleanup_company(company_id, [email] if email else [])
