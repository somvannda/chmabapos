"""Platform-staff moderation of a store's public directory listing.

Nothing previously exercised `PATCH /admin/stores/{id}`, so this covers both the
new moderation field and the fact that the two updatable fields are independent:
unlisting a store must not reactivate it, and reactivating must not relist it.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_admin_attention import cleanup, create_free_workspace, login_headers, promote_to_admin


async def _make_platform_admin(client: AsyncClient, email: str) -> dict:
    register = await client.post(
        "/api/v1/auth/register", json={"email": email, "full_name": "Platform Admin", "password": "strong-password"}
    )
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    await promote_to_admin(email)
    return await login_headers(client, email)


@pytest.mark.asyncio
async def test_staff_can_unlist_a_store_without_deactivating_it() -> None:
    owner_email = f"admin-mod-owner-{uuid.uuid4().hex[:10]}@example.com"
    admin_email = f"admin-mod-staff-{uuid.uuid4().hex[:10]}@example.com"
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            workspace, merchant_headers = await create_free_workspace(client, owner_email)
            company_id = workspace["company"]["id"]
            store_id = workspace["store"]["id"]

            # The merchant publishes and lists their store.
            await client.patch(
                f"/api/v1/stores/{store_id}/public-order", headers=merchant_headers, json={"enabled": True}
            )
            listed = await client.patch(
                f"/api/v1/stores/{store_id}", headers=merchant_headers, json={"listed_in_directory": True}
            )
            assert listed.status_code == 200, listed.text
            company_slug = listed.json()["slug"] if "slug" in listed.json() else None

            current = await client.get("/api/v1/workspaces/current", headers={**merchant_headers, "X-Store-ID": store_id})
            company_slug = current.json()["company"]["slug"]
            store_slug = current.json()["store"]["slug"]

            admin_headers = await _make_platform_admin(client, admin_email)

            # The staff view exposes the moderation fields.
            found = await client.get(f"/api/v1/admin/stores?search={store_id}", headers=admin_headers)
            assert found.status_code == 200, found.text

            # Unlisting keeps the store active: the two fields are independent.
            unlisted = await client.patch(
                f"/api/v1/admin/stores/{store_id}", headers=admin_headers, json={"listed_in_directory": False}
            )
            assert unlisted.status_code == 200, unlisted.text
            assert unlisted.json()["listed_in_directory"] is False
            assert unlisted.json()["is_active"] is True, "unlisting must not deactivate the store"
            assert unlisted.json()["public_order_enabled"] is True

            # ... and it is gone from the public directory.
            public = await client.get(f"/api/v1/public/stores?q={suffix}")
            assert public.json()["total"] == 0, public.text

            # Receiving the store page still works, so a shared link is unaffected.
            page = await client.get(f"/api/v1/public/store/{company_slug}/{store_slug}")
            assert page.status_code == 200, page.text

            # Deactivating does not relist, and relisting does not reactivate.
            deactivated = await client.patch(
                f"/api/v1/admin/stores/{store_id}", headers=admin_headers, json={"is_active": False}
            )
            assert deactivated.json()["is_active"] is False
            assert deactivated.json()["listed_in_directory"] is False

            relisted = await client.patch(
                f"/api/v1/admin/stores/{store_id}", headers=admin_headers, json={"listed_in_directory": True}
            )
            assert relisted.json()["listed_in_directory"] is True
            assert relisted.json()["is_active"] is False, "relisting must not reactivate the store"
    finally:
        await cleanup(owner_email, company_id)
        await cleanup(admin_email, None)
