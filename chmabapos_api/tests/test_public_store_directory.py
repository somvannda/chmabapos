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

            # Listing is a separate, explicit opt-in from taking orders: a store
            # can be orderable from a shared link without being discoverable.
            unlisted = await client.get(f"/api/v1/public/stores?q={suffix}")
            assert unlisted.json()["total"] == 0, unlisted.text

            listed = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}", headers=ctx["headers"], json={"listed_in_directory": True}
            )
            assert listed.status_code == 200, listed.text
            assert listed.json()["listed_in_directory"] is True

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

            # Unlisting removes it from the directory without disabling ordering.
            await client.patch(
                f"/api/v1/stores/{ctx['store_id']}", headers=ctx["headers"], json={"listed_in_directory": False}
            )
            after = await client.get(f"/api/v1/public/stores?q={suffix}")
            assert after.json()["total"] == 0, after.text
            # ... and the store page itself still resolves, so a shared link keeps working.
            page = await client.get(f"/api/v1/public/store/dir-co-{suffix}/visible-{suffix}")
            assert page.status_code == 200, page.text
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_directory_hides_an_opted_in_store_whose_ordering_is_off() -> None:
    """Listing is necessary but not sufficient: online ordering gates it too.

    Settings -> All stores shows both switches side by side, so the pair has to
    be honoured server-side rather than trusted from the UI. A store that opted
    in but cannot take orders is a dead card in the directory.
    """
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Gate Co {suffix}", f"Gated {suffix}", plan="pro", email_prefix="directorygate"
            )
            email, company_id = ctx["email"], ctx["company_id"]

            # Opt in first, then enable ordering: the order an owner works in if
            # they tick "list" before switching the storefront on. Listing alone
            # must not publish a store that has no public page.
            listed = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}", headers=ctx["headers"], json={"listed_in_directory": True}
            )
            assert listed.status_code == 200, listed.text

            hidden = await client.get(f"/api/v1/public/stores?q={suffix}")
            assert hidden.json()["total"] == 0, hidden.text

            enabled = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            assert enabled.status_code == 200, enabled.text
            shown = await client.get(f"/api/v1/public/stores?q={suffix}")
            assert f"Gated {suffix}" in [card["store_name"] for card in shown.json()["stores"]], shown.text

            # Turning ordering back off hides the store again, but the owner's
            # listing choice survives so re-enabling restores it instead of
            # silently unlinking a store whose address may be on signage.
            disabled = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": False}
            )
            assert disabled.status_code == 200, disabled.text
            gone = await client.get(f"/api/v1/public/stores?q={suffix}")
            assert gone.json()["total"] == 0, gone.text

            stores = await client.get("/api/v1/stores", headers=ctx["headers"])
            assert stores.status_code == 200, stores.text
            row = next(store for store in stores.json() if store["id"] == ctx["store_id"])
            assert row["listed_in_directory"] is True
            assert row["public_order_enabled"] is False
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_create_store_can_opt_into_the_directory_up_front() -> None:
    """The Add store form offers listing already ticked for shop types that want it.

    Listing is still the merchant's tick, never inferred from the shop type: a
    request that omits the field keeps the column default (off), so a client that
    never sends it cannot publish a store by accident.
    """
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Ask Co {suffix}", f"Asked {suffix}", plan="pro", email_prefix="directorycreate"
            )
            email, company_id = ctx["email"], ctx["company_id"]

            listed = await client.post(
                "/api/v1/stores",
                headers=ctx["headers"],
                json={"name": f"Ticked {suffix}", "currency_code": "USD", "listed_in_directory": True},
            )
            assert listed.status_code == 201, listed.text
            assert listed.json()["listed_in_directory"] is True

            plain = await client.post(
                "/api/v1/stores",
                headers=ctx["headers"],
                json={"name": f"Unticked {suffix}", "currency_code": "USD"},
            )
            assert plain.status_code == 201, plain.text
            assert plain.json()["listed_in_directory"] is False

            # The tick alone publishes nothing: the directory also needs online
            # ordering, which none of these stores has been given.
            assert (await client.get(f"/api/v1/public/stores?q={suffix}")).json()["total"] == 0
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
