"""Keeping a public order and its kitchen ticket in step when a QR settles late.

A public order is recorded twice: the sale (``orders``/``payments``) and the
kitchen ticket (``held_orders``). Each used to be settled by a different code
path, so a payment discovered by the ticket sweep could leave the sale out of
reporting, while a payment discovered by the till could leave the kitchen board
asking for money already taken. These tests cover both directions, plus the
shopper reopening the status page after closing the payment screen.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.api.v1 import reconcile_open_held_order_payments
from app.db import SessionLocal
from app.main import app
from app.models import HeldOrder, Order, Payment
from app.services.payments.chamabapay import ChmabaPayClient
from tests.test_online_order_payment import LINK, _enable_public_order, _owner_workspace

pytestmark = pytest.mark.asyncio


def _provider_reports_paid(monkeypatch) -> None:
    async def fake_reconcile(self, payment_public_id: str) -> dict:
        return {"status": "PAID", "source": None}

    monkeypatch.setattr(ChmabaPayClient, "reconcile", fake_reconcile)


async def _submit_paid_order(client: AsyncClient, *, stock: int = 5) -> tuple[dict[str, str], dict, str]:
    headers, store_id = await _owner_workspace(client)
    linked = await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": LINK})
    assert linked.status_code == 200, linked.text
    token = await _enable_public_order(client, headers, store_id, True)
    product = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Online Latte", "sku": f"OPR-{uuid.uuid4().hex[:8]}", "price": "3.00", "opening_stock": stock},
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    submitted = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product_id, "quantity": 1}]})
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["payment_status"] == "pending"
    return headers, submitted.json(), product_id


async def _linked_order_id(held_id: str) -> uuid.UUID:
    async with SessionLocal() as db:
        return (await db.execute(select(HeldOrder.order_id).where(HeldOrder.id == uuid.UUID(held_id)))).scalar_one()


async def _assert_both_sides_paid(held_id: str) -> None:
    order_id = await _linked_order_id(held_id)
    async with SessionLocal() as db:
        ticket = await db.get(HeldOrder, uuid.UUID(held_id))
        order = await db.get(Order, order_id)
        payment = (await db.execute(select(Payment).where(Payment.order_id == order_id))).scalars().one()
    assert ticket.payment_status == "paid"
    assert ticket.paid_at is not None
    assert order.status == "paid"
    assert payment.status == "paid"


async def test_the_status_page_settles_a_payment_the_shopper_stopped_watching(monkeypatch) -> None:
    """The shopper closed the tab before the QR landed, then reopened the order link."""
    _provider_reports_paid(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _headers, held, _product_id = await _submit_paid_order(client)

        status = await client.get(f"/api/v1/public/orders/{held['public_token']}")
        assert status.status_code == 200, status.text
        assert status.json()["payment_status"] == "paid"
    await _assert_both_sides_paid(held["id"])


async def test_the_ticket_sweep_settles_the_sale_behind_it(monkeypatch) -> None:
    """The hourly sweep used to mark only the kitchen ticket, leaving reporting unpaid."""
    _provider_reports_paid(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _headers, held, _product_id = await _submit_paid_order(client)

    # The sweep only considers tickets older than its minimum age.
    async with SessionLocal() as db:
        await db.execute(text("UPDATE held_orders SET created_at = now() - interval '10 minutes' WHERE id = :id"), {"id": uuid.UUID(held["id"])})
        await db.commit()
        stats = await reconcile_open_held_order_payments(db)
        await db.commit()
    assert stats["paid"] >= 1
    await _assert_both_sides_paid(held["id"])


async def test_the_merchant_recheck_marks_the_kitchen_ticket_paid(monkeypatch) -> None:
    """Settling from Orders must not leave the board asking for money already taken."""
    _provider_reports_paid(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, held, _product_id = await _submit_paid_order(client)

        recheck = await client.post("/api/v1/orders/recheck-payments", headers=headers)
        assert recheck.status_code == 200, recheck.text
        assert recheck.json()["settled"] == 1
    await _assert_both_sides_paid(held["id"])


async def test_marking_a_public_order_paid_marks_its_ticket() -> None:
    """The manager override goes through the same settlement, ticket included."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, held, _product_id = await _submit_paid_order(client)
        order_id = await _linked_order_id(held["id"])

        result = await client.post(f"/api/v1/orders/{order_id}/mark-paid", headers=headers, json={"note": "bank shows it"})
        assert result.status_code == 200, result.text
        assert result.json()["settled_by"] == "manual"
    await _assert_both_sides_paid(held["id"])


async def test_a_paid_ticket_whose_sale_cannot_complete_is_still_paid(monkeypatch) -> None:
    """The money is real even when the last unit went to another sale.

    The order must stay open for staff to resolve, but the kitchen ticket must
    not go back to asking the shopper for money they already sent.
    """
    _provider_reports_paid(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, held, product_id = await _submit_paid_order(client, stock=1)
        # Sell the last unit at the counter before the QR is discovered.
        cash = await client.post("/api/v1/orders", headers=headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"})
        assert cash.status_code == 201, cash.text
        assert cash.json()["status"] == "paid"

        status = await client.get(f"/api/v1/public/orders/{held['public_token']}")
        assert status.status_code == 200, status.text
        assert status.json()["payment_status"] == "paid"

    order_id = await _linked_order_id(held["id"])
    async with SessionLocal() as db:
        ticket = await db.get(HeldOrder, uuid.UUID(held["id"]))
        order = await db.get(Order, order_id)
        payment = (await db.execute(select(Payment).where(Payment.order_id == order_id))).scalars().one()
    # The ticket takes the money off the screen; the order stays open with its
    # payment pending, so staff can fix stock and settle it from Orders.
    assert ticket.payment_status == "paid"
    assert order.status == "payment_pending"
    assert payment.status == "pending"
