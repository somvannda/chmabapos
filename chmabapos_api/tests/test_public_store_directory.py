"""The public store directory.

`GET /public/stores` is what the directory page reads. It must list only stores
that have actually published a page, and it must page server-side rather than
trying to return every store.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_directory_lists_only_published_stores() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Dir Co {suffix}", f"Visible {suffix}", plan="pro", email_prefix="directory"
            )
            email, company_id = ctx["email"], ctx["company_id"]

            # A second store in the same company that is never published.
            created = await client.post(
                "/api/v1/stores",
                headers=ctx["headers"],
                json={"name": f"Hidden {suffix}", "currency_code": "USD"},
            )
            assert created.status_code == 201, created.text

            published = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            assert published.status_code == 200, published.text

            # The suffix appears in both store names and the company name, so a
            # search on it matches both stores and the company: only the published
            # one may come back.
            listing = await client.get(f"/api/v1/public/stores?q={suffix}")
            assert listing.status_code == 200, listing.text
            body = listing.json()
            names = [card["store_name"] for card in body["stores"]]
            assert f"Visible {suffix}" in names
            assert f"Hidden {suffix}" not in names
            assert body["total"] == 1

            # The card carries what the directory needs, and no PII.
            card = next(entry for entry in body["stores"] if entry["store_name"] == f"Visible {suffix}")
            assert card["company_slug"] == f"dir-co-{suffix}"
            assert card["store_slug"] == f"visible-{suffix}"
            assert card["is_open"] is None  # no hours published yet
            assert card["tagline"] is None  # no branding yet
            assert "email" not in card and "phone" not in card

            # Searching by store name works, not just by company name.
            by_store = await client.get("/api/v1/public/stores?q=Visible")
            assert f"Visible {suffix}" in [entry["store_name"] for entry in by_store.json()["stores"]]

            # Paging is enforced server-side: never more than `limit` back.
            paged = await client.get("/api/v1/public/stores?limit=1&offset=0")
            assert len(paged.json()["stores"]) <= 1
            assert paged.json()["total"] >= 1
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
