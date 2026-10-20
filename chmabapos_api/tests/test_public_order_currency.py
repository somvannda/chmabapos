"""A public order is charged in the store's currency, and never borrows a link.

A merchant pricing in riel needs a KHR ABA PayWay link. Without one the provider
would refuse (`currency_not_configured`), but the dangerous alternative is worse:
falling back to the USD link and taking dollars for a riel price. This pins the
resolution - the store's own link for that currency, then the company's, never the
other currency's - and the message the shopper gets when it cannot be paid.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup

USD_LINK = "https://link.payway.com.kh/ABAPAYusd001"
KHR_LINK = "https://link.payway.com.kh/ABAPAYkhr001"


async def _enable_online_payment(client: AsyncClient, ctx: dict, currency: str) -> str:
    store_id = ctx["store_id"]
    headers = ctx["headers"]
    if currency != "USD":
        # A store can only be priced in a currency its company has enabled.
        currencies = await client.put(
            "/api/v1/settings/currencies", headers=headers, json={"primary_code": "USD", "enabled_codes": ["USD", currency]}
        )
        assert currencies.status_code == 200, currencies.text
    configured = await client.patch(
        f"/api/v1/stores/{store_id}",
        headers=headers,
        json={"currency_code": currency, "preferences": {"public_order_require_payment": True}},
    )
    assert configured.status_code == 200, configured.text
    settings = await client.patch(f"/api/v1/stores/{store_id}/public-order", headers=headers, json={"enabled": True})
    assert settings.status_code == 200, settings.text
    return settings.json()["token"]


@pytest.mark.asyncio
async def test_a_khr_priced_store_needs_a_khr_link_and_never_borrows_usd() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "KHR Store", "Main", plan="pro", email_prefix="khr-currency")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_id = ctx["headers"], ctx["store_id"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={"name": "Riel Latte", "sku": f"KH-{uuid.uuid4().hex[:8]}", "price": "3.00", "category_id": category_id, "opening_stock": 20},
                )
            ).json()
            token = await _enable_online_payment(client, ctx, "KHR")
            body = {"items": [{"product_id": product["id"], "quantity": 1}]}

            # 1. No links at all: refused, and the message names the currency.
            missing = await client.post(f"/api/v1/public/order/{token}", json=body)
            assert missing.status_code == 409, missing.text
            assert "KHR" in missing.json()["detail"], missing.text

            # 2. A USD link alone must NOT be borrowed for a riel price.
            usd_only = await client.patch(
                f"/api/v1/stores/{store_id}", headers=headers, json={"aba_payway_links": {"USD": USD_LINK}}
            )
            assert usd_only.status_code == 200, usd_only.text
            still_missing = await client.post(f"/api/v1/public/order/{token}", json=body)
            assert still_missing.status_code == 409, f"a USD link must not satisfy KHR: {still_missing.text}"

            # 3. The KHR link makes it payable.
            both = await client.patch(
                f"/api/v1/stores/{store_id}", headers=headers, json={"aba_payway_links": {"KHR": KHR_LINK}}
            )
            assert both.status_code == 200, both.text
            paid = await client.post(f"/api/v1/public/order/{token}", json=body)
            assert paid.status_code == 201, paid.text
            assert paid.json()["payment_status"] == "pending"
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_a_usd_priced_store_still_works_with_one_usd_link() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "USD Store", "Main", plan="pro", email_prefix="usd-currency")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_id = ctx["headers"], ctx["store_id"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={"name": "Dollar Latte", "sku": f"UD-{uuid.uuid4().hex[:8]}", "price": "3.00", "category_id": category_id, "opening_stock": 20},
                )
            ).json()
            token = await _enable_online_payment(client, ctx, "USD")
            await client.patch(f"/api/v1/stores/{store_id}", headers=headers, json={"aba_payway_links": {"USD": USD_LINK}})
            order = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product["id"], "quantity": 1}]})
            assert order.status_code == 201, order.text
            assert order.json()["payment_status"] == "pending"
    finally:
        await cleanup_company(company_id, [email] if email else [])
