"""The POS mints KHQR in the store's own currency, or refuses.

Before this, the POS hard-refused KHQR unless both the QR tender and the store
were USD, so a KHR store could not take a riel QR at all. The guard is now a
currency match, and the link is resolved per currency - never the other
currency's link, because a riel QR backed by a dollar merchant account does not
settle.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _store(client: AsyncClient, ctx: dict, *, currency: str, price: str) -> dict:
    headers, store_id = ctx["headers"], ctx["store_id"]
    if currency != "USD":
        enabled = await client.put(
            "/api/v1/settings/currencies", headers=headers, json={"primary_code": "USD", "enabled_codes": ["USD", currency]}
        )
        assert enabled.status_code == 200, enabled.text
        configured = await client.patch(f"/api/v1/stores/{store_id}", headers=headers, json={"currency_code": currency})
        assert configured.status_code == 200, configured.text
    category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
    return (
        await client.post(
            "/api/v1/products",
            headers=ctx["store_headers"],
            json={"name": f"QR {uuid.uuid4().hex[:4]}", "sku": f"QR-{uuid.uuid4().hex[:8]}", "price": price, "category_id": category_id, "opening_stock": 3},
        )
    ).json()


async def _order(client: AsyncClient, ctx: dict, product: dict, tender_currency: str, amount: str):
    return await client.post(
        "/api/v1/orders",
        headers=ctx["store_headers"],
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "tenders": [{"method": "khqr", "currency_code": tender_currency, "amount": amount}],
        },
    )


@pytest.mark.asyncio
async def test_a_khr_store_without_a_khr_link_is_told_which_currency_is_missing() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Riel QR Co", "Main", plan="pro", email_prefix="pos-khr-qr")
            email, company_id = ctx["email"], ctx["company_id"]
            product = await _store(client, ctx, currency="KHR", price="3333")

            response = await _order(client, ctx, product, "KHR", "3333")
            assert response.status_code == 400, response.text
            # The old answer was a blanket "KHQR must be paid in USD"; the merchant
            # needs to know which link to add.
            assert "KHR ABA PayWay link" in response.text, response.text
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_a_usd_store_cannot_mint_a_riel_qr() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Dollar QR Co", "Main", plan="pro", email_prefix="pos-usd-qr")
            email, company_id = ctx["email"], ctx["company_id"]
            product = await _store(client, ctx, currency="USD", price="10")

            response = await _order(client, ctx, product, "KHR", "40000")
            assert response.status_code == 400, response.text
            assert "store's currency (USD)" in response.text, response.text
    finally:
        await cleanup_company(company_id, [email] if email else [])
