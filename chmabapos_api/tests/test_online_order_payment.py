from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app

LINK = "https://link.payway.com.kh/ABAPAYpe518710Y"


async def _owner_workspace(client: AsyncClient) -> tuple[dict[str, str], str]:
    email = f"online-pay-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Online Owner", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Online Pay Co", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    workspace = setup.json()
    return {**headers, "X-Store-ID": workspace["store"]["id"]}, workspace["store"]["id"]


async def _product(client: AsyncClient, headers: dict[str, str]) -> str:
    product = await client.post("/api/v1/products", headers=headers, json={"name": "Online Latte", "sku": f"OL-{uuid.uuid4().hex[:8]}", "price": "3.00", "opening_stock": 5})
    assert product.status_code == 201, product.text
    return product.json()["id"]


async def _enable_public_order(client: AsyncClient, headers: dict[str, str], store_id: str, require_payment: bool) -> str:
    settings = await client.patch(f"/api/v1/stores/{store_id}/public-order", headers=headers, json={"enabled": True, "require_online_payment": require_payment})
    assert settings.status_code == 200, settings.text
    assert settings.json()["enabled"] is True
    return settings.json()["token"]


async def _recorded_amount(external_id: str) -> str:
    """The amount the order actually recorded.

    A webhook event carries the figure the provider says it collected, and the
    webhook refuses to apply an event whose amount disagrees with the order. The
    old hardcoded "3.00" was a placeholder nothing validated until the public
    order started recording a payment of its own.
    """
    async with SessionLocal() as db:
        amount = (await db.execute(text("SELECT amount FROM payments WHERE external_id = :id"), {"id": external_id})).scalar_one()
    return str(amount)


@pytest.mark.asyncio
async def test_online_order_creates_khqr_and_settles_on_payment() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, store_id = await _owner_workspace(client)
        # An active merchant ABA link lets the store take KHQR.
        linked = await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": LINK})
        assert linked.status_code == 200, linked.text
        token = await _enable_public_order(client, headers, store_id, True)
        product_id = await _product(client, headers)

        menu = await client.get(f"/api/v1/public/order/{token}")
        assert menu.status_code == 200, menu.text
        assert menu.json()["require_online_payment"] is True

        submitted = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product_id, "quantity": 1}]})
        assert submitted.status_code == 201, submitted.text
        order = submitted.json()
        assert order["payment_status"] == "pending"
        assert order["payment_qr_string"]
        held_id = order["id"]

        pending = await client.get(f"/api/v1/public/order/{token}/payment/{held_id}")
        assert pending.status_code == 200, pending.text
        assert pending.json()["paid"] is False
        assert pending.json()["payment_status"] == "pending"

        async with SessionLocal() as db:
            external_id = (await db.execute(text("SELECT payment_external_id FROM held_orders WHERE id = :id"), {"id": uuid.UUID(held_id)})).scalar_one()
        assert external_id

        completed = await client.post(f"/api/v1/mock/chamabapay/{external_id}/complete")
        assert completed.status_code == 204, completed.text

        paid = await client.get(f"/api/v1/public/order/{token}/payment/{held_id}")
        assert paid.status_code == 200, paid.text
        assert paid.json()["paid"] is True
        assert paid.json()["payment_status"] == "paid"


@pytest.mark.asyncio
async def test_public_order_without_required_payment_stays_unpaid() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, store_id = await _owner_workspace(client)
        token = await _enable_public_order(client, headers, store_id, False)
        product_id = await _product(client, headers)

        menu = await client.get(f"/api/v1/public/order/{token}")
        assert menu.json()["require_online_payment"] is False
        submitted = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product_id, "quantity": 1}]})
        assert submitted.status_code == 201, submitted.text
        assert submitted.json()["payment_status"] == "unpaid"
        assert submitted.json()["payment_qr_string"] is None


@pytest.mark.asyncio
async def test_webhook_settles_an_online_order(monkeypatch) -> None:
    monkeypatch.setattr("app.api.v1.signature_is_valid", lambda *args, **kwargs: True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, store_id = await _owner_workspace(client)
        linked = await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": LINK})
        assert linked.status_code == 200, linked.text
        token = await _enable_public_order(client, headers, store_id, True)
        product_id = await _product(client, headers)
        submitted = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product_id, "quantity": 1}]})
        assert submitted.status_code == 201, submitted.text
        held_id = submitted.json()["id"]
        async with SessionLocal() as db:
            external_id = (await db.execute(text("SELECT payment_external_id FROM held_orders WHERE id = :id"), {"id": uuid.UUID(held_id)})).scalar_one()

        amount = await _recorded_amount(external_id)
        event = {
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "payment.paid",
            "created": datetime.now(timezone.utc).isoformat(),
            "data": {"payment": {"id": external_id, "status": "paid", "amount": amount, "currency": "USD", "reference_id": "online-test", "approved_at": datetime.now(timezone.utc).isoformat()}},
        }
        hook = await client.post("/api/v1/webhooks/chamabapay", json=event)
        assert hook.status_code == 200, hook.text

        paid = await client.get(f"/api/v1/public/order/{token}/payment/{held_id}")
        assert paid.status_code == 200, paid.text
        assert paid.json()["paid"] is True


async def _board_ids(client, headers):
    board = await client.get("/api/v1/held-orders", headers=headers)
    assert board.status_code == 200, board.text
    return [row["id"] for row in board.json()]


@pytest.mark.asyncio
async def test_board_hides_unpaid_online_order_until_paid(monkeypatch) -> None:
    monkeypatch.setattr("app.api.v1.signature_is_valid", lambda *args, **kwargs: True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, store_id = await _owner_workspace(client)
        assert (await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": LINK})).status_code == 200
        token = await _enable_public_order(client, headers, store_id, True)
        product_id = await _product(client, headers)
        submitted = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product_id, "quantity": 1}]})
        held_id = submitted.json()["id"]

        assert held_id not in await _board_ids(client, headers)

        async with SessionLocal() as db:
            external_id = (await db.execute(text("SELECT payment_external_id FROM held_orders WHERE id = :id"), {"id": uuid.UUID(held_id)})).scalar_one()
        amount = await _recorded_amount(external_id)
        event = {"id": f"evt_{uuid.uuid4().hex}", "type": "payment.paid", "created": datetime.now(timezone.utc).isoformat(), "data": {"payment": {"id": external_id, "status": "paid", "amount": amount, "currency": "USD", "reference_id": "online-test", "approved_at": datetime.now(timezone.utc).isoformat()}}}
        assert (await client.post("/api/v1/webhooks/chamabapay", json=event)).status_code == 200

        assert held_id in await _board_ids(client, headers)


@pytest.mark.asyncio
async def test_board_shows_pay_at_counter_online_order() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, store_id = await _owner_workspace(client)
        token = await _enable_public_order(client, headers, store_id, False)
        product_id = await _product(client, headers)
        submitted = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product_id, "quantity": 1}]})
        assert submitted.status_code == 201, submitted.text
        assert submitted.json()["id"] in await _board_ids(client, headers)


@pytest.mark.asyncio
async def test_required_payment_without_a_merchant_link_is_rejected() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, store_id = await _owner_workspace(client)
        # Require online payment but leave the merchant ABA link unset.
        token = await _enable_public_order(client, headers, store_id, True)
        product_id = await _product(client, headers)

        submitted = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product_id, "quantity": 1}]})
        # The order must not be accepted unpaid when the store requires payment.
        assert submitted.status_code == 409, submitted.text
        assert await _board_ids(client, headers) == []


@pytest.mark.asyncio
async def test_webhook_refuses_an_amount_that_disagrees_with_the_order(monkeypatch) -> None:
    """A provider event claiming another figure must not settle the order.

    A public order now records a payment of its own, which turns the webhook's
    amount check from dormant into load-bearing: before that, no payment row
    existed to compare against and any amount was accepted.
    """
    monkeypatch.setattr("app.api.v1.signature_is_valid", lambda *args, **kwargs: True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, store_id = await _owner_workspace(client)
        assert (await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": LINK})).status_code == 200
        token = await _enable_public_order(client, headers, store_id, True)
        product_id = await _product(client, headers)
        submitted = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product_id, "quantity": 1}]})
        held_id = submitted.json()["id"]
        async with SessionLocal() as db:
            external_id = (await db.execute(text("SELECT payment_external_id FROM held_orders WHERE id = :id"), {"id": uuid.UUID(held_id)})).scalar_one()

        recorded = await _recorded_amount(external_id)
        inflated = f"{Decimal(recorded) + Decimal('1.00'):.2f}"
        event = {"id": f"evt_{uuid.uuid4().hex}", "type": "payment.paid", "created": datetime.now(timezone.utc).isoformat(), "data": {"payment": {"id": external_id, "status": "paid", "amount": inflated, "currency": "USD", "reference_id": "online-test", "approved_at": datetime.now(timezone.utc).isoformat()}}}
        assert (await client.post("/api/v1/webhooks/chamabapay", json=event)).status_code == 400

        unpaid = await client.get(f"/api/v1/public/order/{token}/payment/{held_id}")
        assert unpaid.status_code == 200, unpaid.text
        assert unpaid.json()["paid"] is False


@pytest.mark.asyncio
async def test_a_paid_public_order_is_an_order_of_its_own() -> None:
    """The whole point: a paid online sale is a sale.

    It used to exist only as a held ticket, so nothing that reads orders -
    reporting, refunds, the shopper's own history - could see it until a member
    of staff settled the ticket by hand.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, store_id = await _owner_workspace(client)
        assert (await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": LINK})).status_code == 200
        token = await _enable_public_order(client, headers, store_id, True)
        product_id = await _product(client, headers)
        submitted = await client.post(f"/api/v1/public/order/{token}", json={"items": [{"product_id": product_id, "quantity": 1}]})
        assert submitted.status_code == 201, submitted.text
        held_id = submitted.json()["id"]

        async with SessionLocal() as db:
            placed = (await db.execute(text("SELECT id, status, total, created_by, source, public_token FROM orders WHERE store_id = :sid AND source = 'online'"), {"sid": uuid.UUID(store_id)})).mappings().one()
            external_id = (await db.execute(text("SELECT payment_external_id FROM held_orders WHERE id = :id"), {"id": uuid.UUID(held_id)})).scalar_one()

        # Nobody behind it, priced by the server, and not yet paid.
        assert placed["created_by"] is None
        assert placed["status"] == "payment_pending"
        assert placed["total"] == Decimal("3.30")
        assert placed["public_token"] == submitted.json()["public_token"]
        assert (await client.post(f"/api/v1/mock/chamabapay/{external_id}/complete")).status_code == 204

        async with SessionLocal() as db:
            settled = (await db.execute(text("SELECT status, paid_at FROM orders WHERE id = :id"), {"id": placed["id"]})).mappings().one()
        assert settled["status"] == "paid"
        assert settled["paid_at"] is not None


async def _slugs(store_id: str) -> tuple[str, str]:
    async with SessionLocal() as db:
        row = (await db.execute(text("SELECT c.slug AS company_slug, s.slug AS store_slug FROM stores s JOIN companies c ON c.id = s.company_id WHERE s.id = :sid"), {"sid": uuid.UUID(store_id)})).mappings().one()
    return row["company_slug"], row["store_slug"]


@pytest.mark.asyncio
async def test_the_storefronts_own_route_places_the_same_order() -> None:
    """The storefront addresses a store by slug, not by the public token.

    Both routes delegate to the same submit function, but the slug route is the one a
    shopper actually uses, and nothing tested it: the suite only ever drove the
    token-addressed route that the printed table QR codes depend on. Slugs are allocated
    at workspace setup and made unique, so they are read back rather than assumed.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, store_id = await _owner_workspace(client)
        assert (await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": LINK})).status_code == 200
        await _enable_public_order(client, headers, store_id, True)
        product_id = await _product(client, headers)
        company_slug, store_slug = await _slugs(store_id)
        base = f"/api/v1/public/store/{company_slug}/{store_slug}"

        menu = await client.get(base)
        assert menu.status_code == 200, menu.text

        submitted = await client.post(f"{base}/orders", json={"items": [{"product_id": product_id, "quantity": 1}]})
        assert submitted.status_code == 201, submitted.text
        held_id = submitted.json()["id"]

        async with SessionLocal() as db:
            external_id = (await db.execute(text("SELECT payment_external_id FROM held_orders WHERE id = :id"), {"id": uuid.UUID(held_id)})).scalar_one()
            placed = (await db.execute(text("SELECT status, source, total, public_token FROM orders WHERE store_id = :sid AND source = 'online'"), {"sid": uuid.UUID(store_id)})).mappings().one()
        assert placed["source"] == "online"
        assert placed["status"] == "payment_pending"
        assert placed["total"] == Decimal("3.30")
        assert placed["public_token"] == submitted.json()["public_token"]

        assert (await client.post(f"/api/v1/mock/chamabapay/{external_id}/complete")).status_code == 204
        async with SessionLocal() as db:
            settled_status, paid_at = (await db.execute(text("SELECT status, paid_at FROM orders WHERE store_id = :sid AND source = 'online'"), {"sid": uuid.UUID(store_id)})).one()
        assert settled_status == "paid"
        assert paid_at is not None


@pytest.mark.asyncio
async def test_the_confirmation_polls_the_order_itself() -> None:
    """The shopper's answer comes from the sale, not from the ticket beside it.

    Polling the ticket meant the screen and the books were two records that had to be kept
    in step, and twice they were not: once the order settled while the screen stayed on
    "pending", once the screen cleared while the sale went missing from reporting. This
    poll asks about the order, so there is nothing to keep in step.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, store_id = await _owner_workspace(client)
        assert (await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": LINK})).status_code == 200
        await _enable_public_order(client, headers, store_id, True)
        product_id = await _product(client, headers)
        company_slug, store_slug = await _slugs(store_id)
        submitted = await client.post(
            f"/api/v1/public/store/{company_slug}/{store_slug}/orders",
            json={"items": [{"product_id": product_id, "quantity": 1}]},
        )
        assert submitted.status_code == 201, submitted.text
        order_token = submitted.json()["public_token"]
        held_id = submitted.json()["id"]

        pending = await client.get(f"/api/v1/public/order/{order_token}/payment")
        assert pending.status_code == 200, pending.text
        # A payment's state must never be cacheable, or the poll keeps reading "pending"
        # and tells a shopper to pay for something they already paid for.
        assert pending.headers["cache-control"] == "no-store"
        assert pending.json()["paid"] is False
        assert pending.json()["payment_status"] == "pending"
        assert pending.json()["order_token"] == order_token
        assert pending.json()["order_number"]

        async with SessionLocal() as db:
            external_id = (await db.execute(text("SELECT payment_external_id FROM held_orders WHERE id = :id"), {"id": uuid.UUID(held_id)})).scalar_one()
        assert (await client.post(f"/api/v1/mock/chamabapay/{external_id}/complete")).status_code == 204

        paid = await client.get(f"/api/v1/public/order/{order_token}/payment")
        assert paid.status_code == 200, paid.text
        assert paid.json()["paid"] is True
        assert paid.json()["payment_status"] == "paid"

        # The answer the shopper sees is the same record the books use.
        async with SessionLocal() as db:
            order_status, order_number = (await db.execute(text("SELECT status, order_number FROM orders WHERE public_token = :token"), {"token": order_token})).one()
        assert order_status == "paid"
        assert paid.json()["order_number"] == order_number

        # An unknown token is simply not found - the token is the whole authorisation.
        assert (await client.get("/api/v1/public/order/not-a-real-token/payment")).status_code == 404
