"""The slug-addressed public storefront endpoint.

`GET /public/store/{company_slug}/{store_slug}` is the contract the storefront
app consumes. It must serve exactly what the tokenised legacy link serves, and
must not resolve across tenants.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_public_store_serves_the_menu_by_slug() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Slug Store Co {suffix}", f"Harbour {suffix}", email_prefix="pub-store"
            )
            email, company_id = ctx["email"], ctx["company_id"]
            category_id = (await client.get("/api/v1/categories", headers=ctx["headers"])).json()[0]["id"]
            created = await client.post(
                "/api/v1/products",
                headers=ctx["store_headers"],
                json={
                    "name": "Storefront Latte",
                    "sku": f"SF-{suffix}",
                    "price": "3.75",
                    "category_id": category_id,
                    "opening_stock": 5,
                },
            )
            assert created.status_code == 201, created.text

            company_slug, store_slug = f"slug-store-co-{suffix}", f"harbour-{suffix}"

            # The page is not served until the store opts into online ordering.
            assert (await client.get(f"/api/v1/public/store/{company_slug}/{store_slug}")).status_code == 404

            enabled = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            assert enabled.status_code == 200, enabled.text
            token = enabled.json()["token"]

            page = await client.get(f"/api/v1/public/store/{company_slug}/{store_slug}")
            assert page.status_code == 200, page.text
            body = page.json()
            assert body["store_name"] == f"Harbour {suffix}"
            assert body["company_slug"] == company_slug
            assert body["store_slug"] == store_slug
            assert "Storefront Latte" in [item["name"] for item in body["items"]]

            # Both addresses describe the same store, so neither can drift.
            legacy = await client.get(f"/api/v1/public/order/{token}")
            assert legacy.status_code == 200, legacy.text
            assert legacy.json()["items"] == body["items"]

            # Unknown slugs 404 instead of resolving to somebody else's store.
            assert (await client.get(f"/api/v1/public/store/{company_slug}/nope-{suffix}")).status_code == 404
            assert (await client.get(f"/api/v1/public/store/nope-{suffix}/{store_slug}")).status_code == 404
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
