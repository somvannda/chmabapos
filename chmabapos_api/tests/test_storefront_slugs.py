"""Public storefront slugs end to end: generated on setup, exposed publicly,
validated on edit, unique per scope, and remembered when renamed."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Company, Store
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _company(company_id: str) -> Company:
    async with SessionLocal() as db:
        return (await db.execute(select(Company).where(Company.id == company_id))).scalar_one()


async def _store(store_id: str) -> Store:
    async with SessionLocal() as db:
        return (await db.execute(select(Store).where(Store.id == store_id))).scalar_one()


@pytest.mark.asyncio
async def test_setup_generates_slugs_and_public_menu_exposes_them() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Acme Coffee {suffix}", f"Downtown {suffix}", email_prefix="slug-setup"
            )
            email, company_id = ctx["email"], ctx["company_id"]

            workspace = (await client.get("/api/v1/workspaces/current", headers=ctx["store_headers"])).json()
            assert workspace["company"]["slug"] == f"acme-coffee-{suffix}"
            assert workspace["store"]["slug"] == f"downtown-{suffix}"

            enabled = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            assert enabled.status_code == 200, enabled.text
            token = enabled.json()["token"]

            # The public menu carries the storefront identity, so a legacy
            # /order/<token> link can be redirected without a second request.
            menu = await client.get(f"/api/v1/public/order/{token}")
            assert menu.status_code == 200, menu.text
            assert menu.json()["company_slug"] == f"acme-coffee-{suffix}"
            assert menu.json()["store_slug"] == f"downtown-{suffix}"
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_company_slug_rename_keeps_the_old_slug_in_history() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Rename Co {suffix}", f"Main {suffix}", email_prefix="slug-rename")
            email, company_id = ctx["email"], ctx["company_id"]
            original = (await _company(company_id)).slug
            assert original == f"rename-co-{suffix}"

            renamed = await client.patch("/api/v1/company", headers=ctx["headers"], json={"slug": f"renamed-{suffix}"})
            assert renamed.status_code == 200, renamed.text
            assert renamed.json()["slug"] == f"renamed-{suffix}"

            # The old address is retained so a printed or shared link still resolves.
            assert original in ((await _company(company_id)).previous_slugs or [])
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_invalid_and_reserved_company_slugs_are_rejected() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Validate Co {suffix}", f"Main {suffix}", email_prefix="slug-invalid"
            )
            email, company_id = ctx["email"], ctx["company_id"]

            for bad in ("stores", "Bad Slug!", "ab", "-leading"):
                response = await client.patch("/api/v1/company", headers=ctx["headers"], json={"slug": bad})
                assert response.status_code == 400, f"{bad!r} -> {response.status_code} {response.text}"
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_store_slugs_are_unique_per_company() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(
                client, f"Two Stores {suffix}", f"First {suffix}", plan="pro", email_prefix="slug-unique"
            )
            email, company_id = ctx["email"], ctx["company_id"]
            first_slug = f"first-{suffix}"
            custom = f"custom-{suffix}"

            workspace = (await client.get("/api/v1/workspaces/current", headers=ctx["store_headers"])).json()
            assert workspace["store"]["slug"] == first_slug

            created = await client.post(
                "/api/v1/stores",
                headers=ctx["headers"],
                json={"name": f"Second {suffix}", "currency_code": "USD", "slug": custom},
            )
            assert created.status_code == 201, created.text
            assert created.json()["slug"] == custom
            second_id = created.json()["id"]

            # Another store cannot claim an address that is already held.
            duplicate = await client.post(
                "/api/v1/stores",
                headers=ctx["headers"],
                json={"name": f"Third {suffix}", "currency_code": "USD", "slug": custom},
            )
            assert duplicate.status_code == 409, duplicate.text

            # Neither can a rename.
            steal = await client.patch(
                f"/api/v1/stores/{second_id}", headers=ctx["headers"], json={"slug": first_slug}
            )
            assert steal.status_code == 409, steal.text

            # Renaming to a free address works and remembers the previous one.
            renamed = await client.patch(
                f"/api/v1/stores/{second_id}", headers=ctx["headers"], json={"slug": f"annex-{suffix}"}
            )
            assert renamed.status_code == 200, renamed.text
            assert renamed.json()["slug"] == f"annex-{suffix}"
            assert custom in ((await _store(second_id)).previous_slugs or [])

            # A reserved address is rejected below a company slug too.
            reserved = await client.patch(
                f"/api/v1/stores/{second_id}", headers=ctx["headers"], json={"slug": "order"}
            )
            assert reserved.status_code == 400, reserved.text
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
