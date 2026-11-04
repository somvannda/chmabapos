"""Recovering a KHQR payment that settled without the till noticing.

The provider webhook and the till's own poll normally complete a QR sale. When
both miss - the tab was closed, the webhook was lost, or the provider's status
endpoint disagreed - the customer's money is real but the order sits at
``payment_pending``. These tests cover the two ways out: asking the provider
again (``/orders/recheck-payments``) and a manager recording the payment by
hand (``/orders/{id}/mark-paid``).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import InventoryBalance, Payment, PlatformActivity
from tests.test_chamabapay_flow import _cleanup

pytestmark = pytest.mark.asyncio

PAYWAY_LINK = "https://link.payway.com.kh/ABAPAYpe518710Y"


async def _bootstrap(client: AsyncClient, *, email: str) -> dict:
    """An owner with a paid plan, an active PayWay link and one stocked product."""
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Mark Paid Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Mark Paid Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    workspace = setup.json()
    store_id = workspace["store"]["id"]
    store_headers = {**headers, "X-Store-ID": store_id}

    completed = await client.post(f"/api/v1/mock/chamabapay/{workspace['billing_payment']['external_id']}/complete", headers=headers)
    assert completed.status_code == 204

    linked = await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": PAYWAY_LINK})
    assert linked.status_code == 200 and linked.json()["aba_payway_status"] == "active"

    category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
    product = await client.post(
        "/api/v1/products",
        headers=store_headers,
        json={"name": "Mark Paid Widget", "sku": f"MP-{uuid.uuid4().hex[:8]}", "price": "12.00", "category_id": category_id, "opening_stock": 4, "reorder_point": 0},
    )
    assert product.status_code == 201, product.text
    return {
        "company_id": workspace["company"]["id"],
        "store_id": store_id,
        "headers": headers,
        "store_headers": store_headers,
        "product_id": product.json()["id"],
    }


async def _pending_khqr_order(client: AsyncClient, setup: dict) -> dict:
    order = await client.post("/api/v1/orders", headers=setup["store_headers"], json={"items": [{"product_id": setup["product_id"], "quantity": 1}], "payment_method": "khqr"})
    assert order.status_code == 201, order.text
    assert order.json()["status"] == "payment_pending"
    return order.json()


async def _add_cashier(client: AsyncClient, setup: dict) -> str:
    email = f"mark-paid-cashier-{uuid.uuid4().hex[:10]}@example.com"
    invite = await client.post("/api/v1/team/invitations", headers=setup["headers"], json={"email": email, "role": "cashier", "store_ids": [setup["store_id"]]})
    assert invite.status_code == 201, invite.text
    accepted = await client.post("/api/v1/team/invitations/accept", json={"token": invite.json()["dev_invitation_token"], "full_name": "Mark Paid Cashier", "password": "strong-password"})
    assert accepted.status_code == 200, accepted.text
    return email


async def test_mark_paid_records_the_payment_when_the_provider_cannot_confirm() -> None:
    """The mock provider still reports PENDING, so the manager's override is what settles it."""
    email = f"mark-paid-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            setup = await _bootstrap(client, email=email)
            company_id = setup["company_id"]
            order = await _pending_khqr_order(client, setup)
            assert order["payments"][0]["status"] != "paid"

            result = await client.post(f"/api/v1/orders/{order['id']}/mark-paid", headers=setup["store_headers"], json={"note": "bank shows the $12"})
            assert result.status_code == 200, result.text
            body = result.json()
            assert body["settled_by"] == "manual"
            assert body["order"]["status"] == "paid"
            assert body["order"]["amount_paid"] == body["order"]["total"]

            # The provider row is paid and carries who recorded it, plus the note.
            async with SessionLocal() as db:
                payment = (await db.execute(select(Payment).where(Payment.order_id == uuid.UUID(order["id"])))).scalars().one()
                assert payment.status == "paid"
                assert payment.provider_metadata["manual_settlement"]["note"] == "bank shows the $12"
                assert payment.provider_metadata["manual_settlement"]["by"]
                balance = (await db.execute(select(InventoryBalance).where(InventoryBalance.product_id == uuid.UUID(setup["product_id"])))).scalars().one()
                assert balance.on_hand == Decimal("3.00")
                activity = (await db.execute(select(PlatformActivity).where(PlatformActivity.event_type == "order.marked_paid", PlatformActivity.company_id == uuid.UUID(setup["company_id"])))).scalars().first()
                assert activity is not None

            # A settled order cannot be marked paid a second time.
            again = await client.post(f"/api/v1/orders/{order['id']}/mark-paid", headers=setup["store_headers"], json={})
            assert again.status_code == 409
    finally:
        await _cleanup(email, company_id)


async def test_mark_paid_uses_the_provider_when_it_confirms(monkeypatch) -> None:
    """A provider that now reports PAID settles the sale without a manual override."""
    from app.services.payments.chamabapay import ChmabaPayClient

    async def fake_reconcile(self, payment_public_id: str) -> dict:
        return {"status": "PAID", "source": None}

    monkeypatch.setattr(ChmabaPayClient, "reconcile", fake_reconcile)
    email = f"mark-paid-provider-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            setup = await _bootstrap(client, email=email)
            company_id = setup["company_id"]
            order = await _pending_khqr_order(client, setup)

            result = await client.post(f"/api/v1/orders/{order['id']}/mark-paid", headers=setup["store_headers"], json={})
            assert result.status_code == 200, result.text
            body = result.json()
            assert body["settled_by"] == "provider"
            assert body["order"]["status"] == "paid"

            async with SessionLocal() as db:
                payment = (await db.execute(select(Payment).where(Payment.order_id == uuid.UUID(order["id"])))).scalars().one()
                assert payment.status == "paid"
                assert "manual_settlement" not in (payment.provider_metadata or {})
    finally:
        await _cleanup(email, company_id)


async def test_recheck_payments_settles_a_late_qr(monkeypatch) -> None:
    """Opening the Orders page re-asks the provider, so a closed till self-heals."""
    from app.services.payments.chamabapay import ChmabaPayClient

    async def fake_reconcile(self, payment_public_id: str) -> dict:
        return {"status": "PAID", "source": None}

    monkeypatch.setattr(ChmabaPayClient, "reconcile", fake_reconcile)
    email = f"recheck-payments-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            setup = await _bootstrap(client, email=email)
            company_id = setup["company_id"]
            order = await _pending_khqr_order(client, setup)

            recheck = await client.post("/api/v1/orders/recheck-payments", headers=setup["store_headers"])
            assert recheck.status_code == 200, recheck.text
            assert recheck.json() == {"checked": 1, "settled": 1}

            fresh = await client.get(f"/api/v1/orders/{order['id']}", headers=setup["store_headers"])
            assert fresh.status_code == 200
            assert fresh.json()["status"] == "paid"
    finally:
        await _cleanup(email, company_id)


async def test_mark_paid_is_refused_for_a_cashier() -> None:
    """Recording money by hand is an owner/manager action."""
    email = f"mark-paid-gate-{uuid.uuid4().hex[:10]}@example.com"
    cashier_email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            setup = await _bootstrap(client, email=email)
            company_id = setup["company_id"]
            cashier_email = await _add_cashier(client, setup)
            order = await _pending_khqr_order(client, setup)

            login = await client.post("/api/v1/auth/login", json={"email": cashier_email, "password": "strong-password"})
            cashier_headers = {"Authorization": f"Bearer {login.json()['access_token']}", "X-Store-ID": setup["store_id"]}
            denied = await client.post(f"/api/v1/orders/{order['id']}/mark-paid", headers=cashier_headers, json={})
            assert denied.status_code == 403, denied.text

            # The order is untouched, so the owner can still settle it.
            fresh = await client.get(f"/api/v1/orders/{order['id']}", headers=setup["store_headers"])
            assert fresh.json()["status"] == "payment_pending"
    finally:
        await _cleanup(email, company_id)
        if cashier_email:
            await _cleanup(cashier_email, None)
