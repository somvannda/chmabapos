"""Storefront branding: preset validation, persistence and public resolution."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Store
from tests.test_lifecycle import cleanup_company, register_and_setup

VIOLET = {"brand": "105 87 245", "soft": "240 239 255"}


async def _set_raw_storefront(store_id: str, value: dict | None) -> None:
    """Write the bag directly, simulating data saved by an older release."""
    async with SessionLocal() as db:
        store = (await db.execute(select(Store).where(Store.id == store_id))).scalar_one()
        store.storefront = value
        await db.commit()


@pytest.mark.asyncio
async def test_storefront_branding_round_trips_and_themes_the_public_page() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Brand Co {suffix}", f"Corner {suffix}", email_prefix="brand"
            , plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            store_id = ctx["store_id"]
            company_slug, store_slug = f"brand-co-{suffix}", f"corner-{suffix}"

            enabled = await client.patch(
                f"/api/v1/stores/{store_id}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            assert enabled.status_code == 200, enabled.text

            # Unbranded stores still get a usable accent, so every page looks
            # deliberate rather than unstyled.
            before = (await client.get(f"/api/v1/public/store/{company_slug}/{store_slug}")).json()
            assert before["storefront"] is None
            assert before["accent_key"] == "violet"
            assert before["accent_brand"] == VIOLET["brand"]
            assert before["accent_soft"] == VIOLET["soft"]

            saved = await client.patch(
                f"/api/v1/stores/{store_id}",
                headers=ctx["headers"],
                json={
                    "storefront": {
                        "tagline": "Roasted daily",
                        "accent": "emerald",
                        "banner": "Free delivery over $10",
                        "socials": {"telegram": "@corner", "instagram": "corner"},
                        "policies": {"returns": "Within 7 days"},
                        "hours": [
                            {"day": "mon", "open": "9:00", "close": "21:00"},
                            {"day": "sun", "closed": True},
                        ],
                    }
                },
            )
            assert saved.status_code == 200, saved.text
            stored = saved.json()["storefront"]
            assert stored["tagline"] == "Roasted daily"
            assert stored["accent"] == "emerald"
            # "9:00" is normalised to a zero-padded 24-hour time.
            assert stored["hours"][0]["open"] == "09:00"

            # The public page resolves the chosen preset to token channels.
            after = (await client.get(f"/api/v1/public/store/{company_slug}/{store_slug}")).json()
            assert after["accent_key"] == "emerald"
            assert after["accent_brand"] == "4 120 87"
            assert after["storefront"]["banner"] == "Free delivery over $10"
            assert after["storefront"]["hours"][1]["closed"] is True

            # The editor cannot offer a preset the API would reject.
            accents = await client.get("/api/v1/storefront/accents", headers=ctx["headers"])
            assert accents.status_code == 200, accents.text
            keys = [preset["key"] for preset in accents.json()]
            assert "violet" in keys and "emerald" in keys
            assert all(preset["brand"] and preset["brand_soft"] for preset in accents.json())
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_unknown_accent_falls_back_instead_of_breaking_the_page() -> None:
    """A preset we later remove must not take down a live store page."""
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Legacy Co {suffix}", f"Old {suffix}", email_prefix="brand-legacy"
            , plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            company_slug, store_slug = f"legacy-co-{suffix}", f"old-{suffix}"
            await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            await _set_raw_storefront(ctx["store_id"], {"accent": "chartreuse", "tagline": "Still here"})

            page = await client.get(f"/api/v1/public/store/{company_slug}/{store_slug}")
            assert page.status_code == 200, page.text
            body = page.json()
            assert body["accent_key"] == "violet"
            assert body["accent_brand"] == VIOLET["brand"]
            # The rest of the stored branding still renders.
            assert body["storefront"]["tagline"] == "Still here"
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_storefront_branding_rejects_invalid_values() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Validate Brand {suffix}", f"Shop {suffix}", email_prefix="brand-invalid"
            , plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]

            cases = {
                "unknown accent": {"accent": "chartreuse"},
                "malformed time": {"hours": [{"day": "mon", "open": "9am", "close": "21:00"}]},
                "impossible time": {"hours": [{"day": "mon", "open": "25:00", "close": "21:00"}]},
                "unknown day": {"hours": [{"day": "funday", "open": "09:00", "close": "21:00"}]},
                "duplicate day": {
                    "hours": [
                        {"day": "mon", "open": "09:00", "close": "12:00"},
                        {"day": "mon", "open": "13:00", "close": "18:00"},
                    ]
                },
                "unknown social": {"socials": {"myspace": "x"}},
                "unknown policy": {"policies": {"warranty": "x"}},
            }
            for label, payload in cases.items():
                response = await client.patch(
                    f"/api/v1/stores/{ctx['store_id']}", headers=ctx["headers"], json={"storefront": payload}
                )
                assert response.status_code == 422, f"{label} -> {response.status_code}"
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
