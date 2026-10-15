"""A shopper's own order history.

Orders are linked directly here rather than through the public submit flow, so the
test stays focused on the two things that matter about a history endpoint: that it
shows the caller's orders and nobody else's.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text

from app.db import SessionLocal
from app.main import app
from app.models import HeldOrder, ShopperAccount, Store
from app.security import create_token


async def _make_shopper(email: str | None = None) -> str:
    async with SessionLocal() as db:
        shopper = ShopperAccount(email=email or f"hist-{uuid.uuid4().hex[:10]}@example.com")
        db.add(shopper)
        await db.commit()
        return str(shopper.id)


async def _link_order(shopper_id: str, *, subtotal: str, label: str) -> str:
    async with SessionLocal() as db:
        store_id = await db.scalar(Store.__table__.select().with_only_columns(Store.id).limit(1))
        held = HeldOrder(
            store_id=store_id,
            created_by=None,
            label=label,
            status="open",
            source="online",
            public_token=uuid.uuid4().hex,
            shopper_id=uuid.UUID(shopper_id),
            items=[
                {
                    "line_key": "line-1",
                    "product_id": str(uuid.uuid4()),
                    "product_name": "History Latte",
                    "quantity": "1",
                    "unit_price": subtotal,
                    "line_total": subtotal,
                }
            ],
        )
        db.add(held)
        await db.commit()
        return str(held.id)


async def _purge(shopper_id: str) -> None:
    async with SessionLocal() as db:
        await db.execute(delete(HeldOrder).where(HeldOrder.shopper_id == uuid.UUID(shopper_id)))
        await db.execute(text("DELETE FROM shopper_accounts WHERE id = :i"), {"i": shopper_id})
        await db.commit()


@pytest.mark.asyncio
async def test_a_shopper_sees_only_their_own_orders() -> None:
    mine = await _make_shopper()
    theirs = await _make_shopper()
    try:
        linked = await _link_order(mine, subtotal="7.50", label="Online order")
        # An order belonging to somebody else, which must not appear.
        await _link_order(theirs, subtotal="99.00", label="Someone else's")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = create_token(uuid.UUID(mine), token_type="shopper")
            response = await client.get(
                "/api/v1/public/auth/orders", headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200, response.text
            rows = response.json()

        assert len(rows) == 1, f"only the caller's own order should be listed: {rows}"
        row = rows[0]
        assert row["label"] == "Online order"
        assert row["subtotal"] == "7.50"
        assert row["status"] == "open"
        # The tracking token is included so the UI can link to the status page...
        assert row["public_token"]
        # ... but nothing staff-facing leaks into a customer's history.
        for leaked in ("id", "store_id", "created_by", "items", "table_id", "cashier_name"):
            assert leaked not in row, f"{leaked} must not be exposed to a shopper"
        assert linked
    finally:
        await _purge(mine)
        await _purge(theirs)


@pytest.mark.asyncio
async def test_order_history_requires_a_shopper_token() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # No token at all.
        assert (await client.get("/api/v1/public/auth/orders")).status_code == 401

        # A token of the wrong kind: this one is signed like a staff access token.
        staff_like = create_token(uuid.uuid4())
        wrong = await client.get(
            "/api/v1/public/auth/orders", headers={"Authorization": f"Bearer {staff_like}"}
        )
        assert wrong.status_code == 401, "a staff-shaped token must not read a shopper's history"
