from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _create_product(client, store_headers, category_id: str, name: str, price: str, stock: int = 0) -> dict:
    response = await client.post(
        "/api/v1/products",
        headers=store_headers,
        json={"name": name, "sku": f"TI-{uuid.uuid4().hex[:8]}", "price": price, "category_id": category_id, "opening_stock": stock},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _on_hand(client, store_headers, product_id: str) -> float:
    products = (await client.get("/api/v1/products", headers=store_headers)).json()
    return next(product["on_hand"] for product in products if product["id"] == product_id)


@pytest.mark.asyncio
async def test_trade_in_intakes_stock_at_assessed_value_and_voids() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Trade-in Store", "Main", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            used_phone = await _create_product(client, store_headers, category_id, "iPhone 13 (used)", "500.00", stock=0)

            created = await client.post(
                "/api/v1/trade-ins",
                headers=store_headers,
                json={"product_id": used_phone["id"], "serial_number": f"TRD-{uuid.uuid4().hex[:8]}", "imei": "356789012345678", "condition_grade": "good", "battery_health": 88, "assessed_value": "300.00", "kind": "trade_in"},
            )
            assert created.status_code == 201, created.text
            trade_in = created.json()
            assert trade_in["status"] == "accepted"
            assert trade_in["assessed_value"] == "300.00"
            assert trade_in["serial_id"]

            # The device is now a graded serial on the shelf, stocked at the value.
            serials = (await client.get(f"/api/v1/products/{used_phone['id']}/serials", headers=store_headers)).json()
            assert len(serials) == 1
            assert serials[0]["status"] == "in_stock"
            assert serials[0]["condition_grade"] == "good"
            assert serials[0]["cost_price"] == "300.00"
            assert await _on_hand(client, store_headers, used_phone["id"]) == 1

            # Voiding pulls the unit back out before it is used or sold.
            voided = await client.post(f"/api/v1/trade-ins/{trade_in['id']}/void", headers=store_headers)
            assert voided.status_code == 200, voided.text
            assert voided.json()["status"] == "void"
            assert await _on_hand(client, store_headers, used_phone["id"]) == 0
            assert (await client.get(f"/api/v1/products/{used_phone['id']}/serials", headers=store_headers)).json() == []
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_trade_in_credit_settles_an_order_once() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Trade-in Sale", "Main", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            # No tax, so the trade-in + cash must equal the item price exactly.
            await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"service_tax_rate": 0})
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            used_phone = await _create_product(client, store_headers, category_id, "Pixel 7 (used)", "400.00", stock=0)
            case = await _create_product(client, store_headers, category_id, "Phone Case", "50.00", stock=5)

            trade_in = (await client.post(
                "/api/v1/trade-ins",
                headers=store_headers,
                json={"product_id": used_phone["id"], "serial_number": f"TRD-{uuid.uuid4().hex[:8]}", "assessed_value": "30.00"},
            )).json()

            sale = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": case["id"], "quantity": 1}], "tenders": [
                    {"method": "trade_in", "currency_code": "USD", "amount": "30.00", "trade_in_id": trade_in["id"]},
                    {"method": "cash", "currency_code": "USD", "amount": "20.00"},
                ]},
            )
            assert sale.status_code == 201, sale.text
            assert sale.json()["total"] == "50.00"

            # The credit is now spent and cannot be reused.
            applied = (await client.get(f"/api/v1/trade-ins/{trade_in['id']}", headers=store_headers)).json()
            assert applied["order_id"] == sale.json()["id"]

            reuse = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": case["id"], "quantity": 1}], "tenders": [
                    {"method": "trade_in", "currency_code": "USD", "amount": "30.00", "trade_in_id": trade_in["id"]},
                    {"method": "cash", "currency_code": "USD", "amount": "20.00"},
                ]},
            )
            assert reuse.status_code == 400
    finally:
        await cleanup_company(company_id, [email] if email else [])
