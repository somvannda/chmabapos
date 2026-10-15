"""Attributing a public order to a signed-in shopper.

The risk here is not that attribution fails but that it *breaks guest checkout*.
So the test spends as much effort on the orders that must still succeed with no
usable token as on the one that gets attributed.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.models import ShopperAccount
from app.security import create_token
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _make_shopper(email: str) -> str:
    async with SessionLocal() as db:
        shopper = ShopperAccount(email=email)
        db.add(shopper)
        await db.commit()
        return str(shopper.id)


async def _purge_shopper(shopper_id: str | None) -> None:
    if not shopper_id:
        return
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM shopper_accounts WHERE id = :i"), {"i": shopper_id})
        await db.commit()


@pytest.mark.asyncio
async def test_a_signed_in_order_is_attributed_while_guests_still_order() -> None:
    owner_email: str | None = None
    company_id: str | None = None
    shopper_id: str | None = None
    shopper_email = f"wire-shopper-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Wire Co {suffix}", f"Till {suffix}", email_prefix="wire")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            category_id = (await client.get("/api/v1/categories", headers=ctx["headers"])).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={
                        "name": "Wire Latte",
                        "sku": f"WR-{suffix}",
                        "price": "3.00",
                        "category_id": category_id,
                        "opening_stock": 10,
                    },
                )
            ).json()
            await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            current = (await client.get("/api/v1/workspaces/current", headers=ctx["store_headers"])).json()
            endpoint = f"/api/v1/public/store/{current['company']['slug']}/{current['store']['slug']}/orders"
            payload = {"items": [{"product_id": product["id"], "quantity": 1}]}

            # 1. A guest order: no token at all. Guest checkout is the default, so
            #    this must keep working.
            guest = await client.post(endpoint, json=payload)
            assert guest.status_code == 201, guest.text

            # 2. A token that is not usable must be ignored, not refused. A stale
            #    token in a browser is not a reason to lose a sale.
            stale = await client.post(endpoint, json=payload, headers={"Authorization": "Bearer not-a-real-token"})
            assert stale.status_code == 201, stale.text

            # 3. A signed-in shopper's order is attributed.
            shopper_id = await _make_shopper(shopper_email)
            token = create_token(uuid.UUID(shopper_id), token_type="shopper")
            signed = await client.post(endpoint, json=payload, headers={"Authorization": f"Bearer {token}"})
            assert signed.status_code == 201, signed.text

            history = await client.get(
                "/api/v1/public/auth/orders", headers={"Authorization": f"Bearer {token}"}
            )
            assert history.status_code == 200, history.text
            rows = history.json()
            assert len(rows) == 1, f"only the attributed order belongs in history: {rows}"
            assert rows[0]["public_token"] == signed.json()["public_token"]
            # The two un-attributed orders are not in it, even though they exist.
            assert guest.json()["public_token"] not in [row["public_token"] for row in rows]
    finally:
        if company_id:
            await cleanup_company(company_id, [owner_email] if owner_email else [])
        await _purge_shopper(shopper_id)
