"""Directory filtering by business type, and the facet that drives the chips."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_directory_filters_by_vertical_and_reports_the_facet() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Filter Co {suffix}", f"Table {suffix}", email_prefix="directory-filter"
            )
            email, company_id = ctx["email"], ctx["company_id"]

            await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            await client.patch(
                f"/api/v1/stores/{ctx['store_id']}", headers=ctx["headers"], json={"listed_in_directory": True}
            )
            changed = await client.patch(
                "/api/v1/company", headers=ctx["headers"], json={"vertical": "restaurant"}
            )
            assert changed.status_code == 200, changed.text

            # The card carries the business type, and the facet drives the chips.
            listing = await client.get(f"/api/v1/public/stores?q={suffix}")
            assert listing.status_code == 200, listing.text
            body = listing.json()
            assert body["total"] == 1, body
            assert body["stores"][0]["vertical"] == "restaurant"
            # The card carries a freshness value, which the sitemap uses as lastmod
            # so a crawler can tell a store that just changed from one that has not
            # moved in months. Asserted as an ISO-8601 shape rather than parsed, to
            # avoid depending on the serialisation details.
            assert body["stores"][0]["updated_at"], body["stores"][0]
            assert "T" in body["stores"][0]["updated_at"]
            assert "restaurant" in body["verticals"]

            # Selecting the matching type keeps it.
            matching = await client.get(f"/api/v1/public/stores?q={suffix}&vertical=restaurant")
            assert matching.json()["total"] == 1, matching.text
            # The facet ignores the vertical filter, so the other chips remain
            # available on the filtered page rather than disappearing.
            assert "restaurant" in matching.json()["verticals"]

            # Selecting a different type excludes it.
            other = await client.get(f"/api/v1/public/stores?q={suffix}&vertical=coffee")
            assert other.json()["total"] == 0, other.text
            # ... but still reports the facet, which is the whole point.
            assert "restaurant" in other.json()["verticals"]
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
