"""Signing in attaches the guest's past orders *and* the merchant's customer row.

The merge itself (guest orders onto the shopper) already existed. This covers the
half that did not: the merchant's own ``customers`` record for the same person was
left unlinked, so a registered shopper looked like an anonymous walk-in at the
counter.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.models import ShopperAccount, ShopperEmailCode
from app.security import hash_opaque_token
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _make_shopper_with_code(email: str, code: str) -> str:
    """A shopper plus a live sign-in code, so the verify endpoint can be driven."""
    async with SessionLocal() as db:
        shopper = ShopperAccount(email=email)
        db.add(shopper)
        await db.flush()
        db.add(
            ShopperEmailCode(
                shopper_id=shopper.id,
                token_hash=hash_opaque_token(code),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            )
        )
        await db.commit()
        return str(shopper.id)


async def _purge_shopper(shopper_id: str | None) -> None:
    if not shopper_id:
        return
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM shopper_accounts WHERE id = :i"), {"i": shopper_id})
        await db.commit()


def _customer_rows(body):
    return body if isinstance(body, list) else body.get("items", [])


@pytest.mark.asyncio
async def test_signing_in_links_the_guest_order_and_the_merchant_customer_row() -> None:
    owner_email: str | None = None
    company_id: str | None = None
    shopper_id: str | None = None
    buyer = f"link-shopper-{uuid.uuid4().hex[:10]}@example.com"
    code = "424242"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Link Co {suffix}", f"Till {suffix}", email_prefix="link")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            category_id = (await client.get("/api/v1/categories", headers=ctx["headers"])).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={"name": "Link Latte", "sku": f"LK-{suffix}", "price": "3.00", "category_id": category_id, "opening_stock": 10},
                )
            ).json()
            await client.patch(f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True})
            current = (await client.get("/api/v1/workspaces/current", headers=ctx["store_headers"])).json()
            endpoint = f"/api/v1/public/store/{current['company']['slug']}/{current['store']['slug']}/orders"

            # A guest order that left an acknowledgement email. That email is the
            # only place the address is recorded, so it is the join key.
            guest = await client.post(
                endpoint,
                json={"items": [{"product_id": product["id"], "quantity": 1}], "customer_email": buyer, "customer_name": "Link Buyer"},
            )
            assert guest.status_code == 201, guest.text
            public_token = guest.json()["public_token"]

            # The account exists but is unverified; the code is what proves the address.
            shopper_id = await _make_shopper_with_code(buyer, code)
            verified = await client.post("/api/v1/public/auth/verify", json={"email": buyer, "code": code})
            assert verified.status_code == 200, verified.text
            token = verified.json()["access_token"]

            # 1. The guest order is now in the shopper's history.
            history = (await client.get("/api/v1/public/auth/orders", headers={"Authorization": f"Bearer {token}"})).json()
            assert [row["public_token"] for row in history] == [public_token], history

            # 2. The merchant's customer list recognises the shopper.
            rows = _customer_rows((await client.get("/api/v1/customers", headers=ctx["store_headers"])).json())
            linked = [row for row in rows if (row.get("email") or "").lower() == buyer]
            assert linked, f"no customer row for {buyer}: {rows}"
            assert linked[0]["shopper_id"] == shopper_id
    finally:
        if company_id:
            await cleanup_company(company_id, [owner_email] if owner_email else [])
        await _purge_shopper(shopper_id)


@pytest.mark.asyncio
async def test_a_different_address_does_not_take_the_order_or_the_customer_row() -> None:
    """The merge key is a *verified* address; someone else's sign-in must not move it."""
    owner_email: str | None = None
    company_id: str | None = None
    other_shopper_id: str | None = None
    buyer = f"owner-shopper-{uuid.uuid4().hex[:10]}@example.com"
    intruder = f"intruder-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Safe Co {suffix}", f"Till {suffix}", email_prefix="safe")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            category_id = (await client.get("/api/v1/categories", headers=ctx["headers"])).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={"name": "Safe Latte", "sku": f"SF-{suffix}", "price": "3.00", "category_id": category_id, "opening_stock": 10},
                )
            ).json()
            await client.patch(f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True})
            current = (await client.get("/api/v1/workspaces/current", headers=ctx["store_headers"])).json()
            endpoint = f"/api/v1/public/store/{current['company']['slug']}/{current['store']['slug']}/orders"

            guest = await client.post(endpoint, json={"items": [{"product_id": product["id"], "quantity": 1}], "customer_email": buyer})
            assert guest.status_code == 201, guest.text

            # A different address signs in.
            other_shopper_id = await _make_shopper_with_code(intruder, "135790")
            verified = await client.post("/api/v1/public/auth/verify", json={"email": intruder, "code": "135790"})
            assert verified.status_code == 200, verified.text
            token = verified.json()["access_token"]

            # The order is not theirs...
            history = (await client.get("/api/v1/public/auth/orders", headers={"Authorization": f"Bearer {token}"})).json()
            assert history == [], history

            # ...and no customer row was invented for them.
            rows = _customer_rows((await client.get("/api/v1/customers", headers=ctx["store_headers"])).json())
            assert not [row for row in rows if (row.get("email") or "").lower() == intruder], rows
    finally:
        if company_id:
            await cleanup_company(company_id, [owner_email] if owner_email else [])
        await _purge_shopper(other_shopper_id)
