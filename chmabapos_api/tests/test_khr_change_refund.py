"""Change and refunds stay in whole riel on a KHR sale.

The checkout now rounds the chargeable total (#937). The two figures that leave a
sale are the change handed back and the refund paid out - both are money the
customer physically receives, so a fractional riel there is just as wrong as a
fractional price.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


def _whole(value: str | int | Decimal) -> bool:
    return Decimal(str(value)) == Decimal(str(value)).to_integral_value()


async def _khr_store_with_item(client: AsyncClient, ctx: dict, price: str) -> tuple[dict, str]:
    headers, store_id = ctx["headers"], ctx["store_id"]
    currencies = await client.put(
        "/api/v1/settings/currencies", headers=headers, json={"primary_code": "USD", "enabled_codes": ["USD", "KHR"]}
    )
    assert currencies.status_code == 200, currencies.text
    configured = await client.patch(f"/api/v1/stores/{store_id}", headers=headers, json={"currency_code": "KHR", "service_tax_rate": 10})
    assert configured.status_code == 200, configured.text
    category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
    product = (
        await client.post(
            "/api/v1/products",
            headers=ctx["store_headers"],
            json={"name": f"Riel Item {uuid.uuid4().hex[:4]}", "sku": f"KH-{uuid.uuid4().hex[:8]}", "price": price, "category_id": category_id, "opening_stock": 5},
        )
    ).json()
    return product, store_id


@pytest.mark.asyncio
async def test_change_on_a_khr_sale_is_whole_riel() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Change Co", "Main", plan="pro", email_prefix="khr-change")
            email, company_id = ctx["email"], ctx["company_id"]
            product, _store_id = await _khr_store_with_item(client, ctx, "3333")

            order = await client.post(
                "/api/v1/orders",
                headers=ctx["store_headers"],
                json={
                    "items": [{"product_id": product["id"], "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "KHR", "amount": "3700"}],
                },
            )
            assert order.status_code == 201, order.text
            body = order.json()
            assert Decimal(body["total"]) == Decimal("3666"), body
            assert body["change_currency_code"] == "KHR", body
            assert _whole(body["change_amount"]), f"fractional riel change: {body['change_amount']}"
            assert Decimal(body["change_amount"]) == Decimal("34"), body
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_a_khr_refund_is_whole_riel() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Refund Co", "Main", plan="pro", email_prefix="khr-refund")
            email, company_id = ctx["email"], ctx["company_id"]
            product, _store_id = await _khr_store_with_item(client, ctx, "3333")

            order = await client.post(
                "/api/v1/orders",
                headers=ctx["store_headers"],
                json={
                    "items": [{"product_id": product["id"], "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "KHR", "amount": "3666"}],
                },
            )
            assert order.status_code == 201, order.text
            order_id = order.json()["id"]

            refund = await client.post(
                f"/api/v1/orders/{order_id}/refund",
                headers=ctx["store_headers"],
                json={"method": "original", "items": [{"product_id": product["id"], "quantity": 1}]},
            )
            assert refund.status_code == 201, refund.text
            body = refund.json()
            assert _whole(body["total"]), f"fractional riel refund: {body['total']}"
            assert Decimal(body["total"]) == Decimal("3666"), body
    finally:
        await cleanup_company(company_id, [email] if email else [])
