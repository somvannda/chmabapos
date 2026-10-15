"""Attaching earlier guest orders when a shopper confirms their address.

The match goes through the acknowledgement email, not the order, so this also
asserts the thing that would be easy to get wrong: that an order already belonging
to somebody is never reassigned.
"""
from __future__ import annotations

import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend, HeldOrder
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _signin_code(email: str) -> str:
    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(EmailSend)
                .where(EmailSend.recipient_email == email, EmailSend.source == "shopper_signin")
                .order_by(EmailSend.created_at.desc())
            )
        ).scalars().first()
    assert row is not None, "a sign-in code should have been queued"
    match = re.search(r"<strong>(\d{6})</strong>", row.body_html or "")
    assert match, row.body_html
    return match.group(1)


async def _order_by_token(token: str) -> HeldOrder | None:
    async with SessionLocal() as db:
        return (await db.execute(select(HeldOrder).where(HeldOrder.public_token == token))).scalar_one_or_none()


async def _purge_shopper(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM shopper_email_codes WHERE shopper_id IN (SELECT id FROM shopper_accounts WHERE email = :e)"), {"e": email})
        await db.execute(text("UPDATE held_orders SET shopper_id = NULL WHERE shopper_id IN (SELECT id FROM shopper_accounts WHERE email = :e)"), {"e": email})
        await db.execute(text("DELETE FROM shopper_accounts WHERE email = :e"), {"e": email})
        await db.commit()


@pytest.mark.asyncio
async def test_confirming_an_address_attaches_earlier_guest_orders() -> None:
    owner_email: str | None = None
    company_id: str | None = None
    buyer = f"merge-buyer-{uuid.uuid4().hex[:10]}@example.com"
    other_buyer = f"merge-other-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Merge Co {suffix}", f"Till {suffix}", email_prefix="merge")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            category_id = (await client.get("/api/v1/categories", headers=ctx["headers"])).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={
                        "name": "Merge Latte",
                        "sku": f"MG-{suffix}",
                        "price": "2.50",
                        "category_id": category_id,
                        "opening_stock": 20,
                    },
                )
            ).json()
            await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            current = (await client.get("/api/v1/workspaces/current", headers=ctx["store_headers"])).json()
            endpoint = f"/api/v1/public/store/{current['company']['slug']}/{current['store']['slug']}/orders"
            items = {"items": [{"product_id": product["id"], "quantity": 1}]}

            # A guest order placed with the buyer's address. No token: guest checkout.
            guest = await client.post(endpoint, json={**items, "customer_email": buyer})
            assert guest.status_code == 201, guest.text
            guest_token = guest.json()["public_token"]

            # An order placed with somebody else's address, which must not be caught.
            foreign = await client.post(endpoint, json={**items, "customer_email": other_buyer})
            foreign_token = foreign.json()["public_token"]

            # Unattributed before the address is confirmed.
            assert (await _order_by_token(guest_token)).shopper_id is None

            # Now the buyer signs in with that address.
            requested = await client.post("/api/v1/public/auth/email-code", json={"email": buyer})
            assert requested.status_code == 202, requested.text
            code = await _signin_code(buyer)
            verified = await client.post("/api/v1/public/auth/verify", json={"email": buyer, "code": code})
            assert verified.status_code == 200, verified.text
            token = verified.json()["access_token"]

            # The earlier guest order is now theirs...
            assert (await _order_by_token(guest_token)).shopper_id is not None
            # ... and the one placed with a different address is not.
            assert (await _order_by_token(foreign_token)).shopper_id is None

            history = await client.get("/api/v1/public/auth/orders", headers={"Authorization": f"Bearer {token}"})
            assert history.status_code == 200, history.text
            listed = [row["public_token"] for row in history.json()]
            assert guest_token in listed, f"the attached order should appear in history: {listed}"
            assert foreign_token not in listed
    finally:
        if company_id:
            await cleanup_company(company_id, [owner_email] if owner_email else [])
        await _purge_shopper(buyer)
        await _purge_shopper(other_buyer)


@pytest.mark.asyncio
async def test_an_order_already_owned_is_never_reassigned() -> None:
    """The guard that matters: a merge must not take an order from its owner."""
    owner_email: str | None = None
    company_id: str | None = None
    buyer = f"merge-guard-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Guard Co {suffix}", f"Till {suffix}", email_prefix="merge-guard")
            owner_email, company_id = ctx["email"], ctx["company_id"]
            category_id = (await client.get("/api/v1/categories", headers=ctx["headers"])).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={
                        "name": "Guard Latte",
                        "sku": f"GD-{suffix}",
                        "price": "2.50",
                        "category_id": category_id,
                        "opening_stock": 20,
                    },
                )
            ).json()
            await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            current = (await client.get("/api/v1/workspaces/current", headers=ctx["store_headers"])).json()
            endpoint = f"/api/v1/public/store/{current['company']['slug']}/{current['store']['slug']}/orders"

            submitted = await client.post(endpoint, json={"items": [{"product_id": product["id"], "quantity": 1}], "customer_email": buyer})
            guest_token = submitted.json()["public_token"]

            # Give it an owner that is not the buyer.
            async with SessionLocal() as db:
                other = await db.execute(text("INSERT INTO shopper_accounts (id, email, is_email_verified, is_active, created_at, updated_at) VALUES (gen_random_uuid(), :e, false, true, now(), now()) RETURNING id"), {"e": f"owner-{uuid.uuid4().hex[:10]}@example.com"})
                owner_id = other.scalar_one()
                await db.execute(text("UPDATE held_orders SET shopper_id = :s WHERE public_token = :t"), {"s": owner_id, "t": guest_token})
                await db.commit()

            # The buyer then confirms the same address.
            await client.post("/api/v1/public/auth/email-code", json={"email": buyer})
            code = await _signin_code(buyer)
            assert (await client.post("/api/v1/public/auth/verify", json={"email": buyer, "code": code})).status_code == 200

            # The order still belongs to whoever had it.
            held = await _order_by_token(guest_token)
            assert str(held.shopper_id) == str(owner_id), "an attributed order must not be reassigned"
    finally:
        if company_id:
            await cleanup_company(company_id, [owner_email] if owner_email else [])
        await _purge_shopper(buyer)
