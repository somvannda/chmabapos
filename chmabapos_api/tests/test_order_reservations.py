from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _on_hand(client: AsyncClient, store_headers: dict[str, str], product_id: str) -> float:
    products = (await client.get("/api/v1/products", headers=store_headers)).json()
    return next(product["on_hand"] for product in products if product["id"] == product_id)


async def _make_product(client: AsyncClient, store_headers: dict[str, str], price: str, opening_stock: int) -> str:
    product = await client.post(
        "/api/v1/products",
        headers=store_headers,
        json={"name": f"Reserved {uuid.uuid4().hex[:6]}", "sku": f"RS-{uuid.uuid4().hex[:8]}", "price": price, "opening_stock": opening_stock},
    )
    assert product.status_code == 201, product.text
    return product.json()["id"]


def _pickup(offset_hours: int = 24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=offset_hours)).isoformat()


@pytest.mark.asyncio
async def test_deposit_reservation_holds_stock_and_collects_the_balance() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Reservation Store", "Main Counter")
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "100.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "30.00"}],
                    "pickup_at": _pickup(),
                    "pickup_note": "collect tomorrow morning",
                    "hold_stock": True,
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()
            assert body["status"] == "pending_pickup"
            assert float(body["deposit"]) == 30.0
            assert float(body["amount_paid"]) == 30.0
            assert body["stock_held"] is True
            assert body["pickup_note"] == "collect tomorrow morning"
            balance = float(body["balance_due"])
            assert balance == round(float(body["total"]) - 30.0, 2)

            # Real stock is held: the unit is off the shelf.
            assert await _on_hand(client, store_headers, product_id) == 4

            collected = await client.post(
                f"/api/v1/orders/{body['id']}/collect",
                headers=store_headers,
                json={"tenders": [{"method": "cash", "currency_code": "USD", "amount": f"{balance:.2f}"}]},
            )
            assert collected.status_code == 200, collected.text
            done = collected.json()
            assert done["status"] == "paid"
            assert float(done["balance_due"]) == 0.0
            assert done["paid_at"] is not None
            # Collection must not draw the held unit down a second time.
            assert await _on_hand(client, store_headers, product_id) == 4

            fetched = await client.get(f"/api/v1/orders/{body['id']}", headers=store_headers)
            assert fetched.status_code == 200, fetched.text
            assert fetched.json()["status"] == "paid"
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_reservation_without_stock_hold_leaves_inventory_until_pickup() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "No Hold Store", "Main")
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "50.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 2}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "10.00"}],
                    "pickup_at": _pickup(48),
                    "hold_stock": False,
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()
            assert body["status"] == "pending_pickup"
            assert body["stock_held"] is False
            # Nothing is held, so the shelf is untouched until collection.
            assert await _on_hand(client, store_headers, product_id) == 5

            balance = float(body["balance_due"])
            collected = await client.post(
                f"/api/v1/orders/{body['id']}/collect",
                headers=store_headers,
                json={"tenders": [{"method": "cash", "currency_code": "USD", "amount": f"{balance:.2f}"}]},
            )
            assert collected.status_code == 200, collected.text
            assert collected.json()["status"] == "paid"
            assert await _on_hand(client, store_headers, product_id) == 3
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_cancelling_a_reservation_returns_held_stock() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Cancel Reservation Store", "Main")
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "40.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 3}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "10.00"}],
                    "pickup_at": _pickup(),
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()
            assert await _on_hand(client, store_headers, product_id) == 2

            cancelled = await client.post(f"/api/v1/orders/{body['id']}/cancel", headers=store_headers, json={})
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["status"] == "cancelled"
            assert cancelled.json()["stock_held"] is False
            assert await _on_hand(client, store_headers, product_id) == 5
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_partial_payment_without_a_pickup_date_is_still_rejected() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "No Pickup Store", "Main")
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "100.00", 5)

            response = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "30.00"}],
                },
            )
            assert response.status_code == 400, response.text
            assert "short" in response.json()["detail"].lower()
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_lapsed_reservation_releases_held_stock_on_read() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Expiry Store", "Main")
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "30.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 2}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "10.00"}],
                    "pickup_at": _pickup(48),
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()
            assert await _on_hand(client, store_headers, product_id) == 3

            # Force the pickup window to have lapsed; the sweep runs on read.
            async with SessionLocal() as db:
                await db.execute(text("UPDATE orders SET reservation_expires_at = now() - interval '1 hour' WHERE id = :order_id"), {"order_id": uuid.UUID(body["id"])})
                await db.commit()

            listing = await client.get("/api/v1/orders", headers=store_headers)
            assert listing.status_code == 200, listing.text
            fetched = await client.get(f"/api/v1/orders/{body['id']}", headers=store_headers)
            assert fetched.json()["status"] == "reservation_expired"
            assert fetched.json()["stock_held"] is False
            assert await _on_hand(client, store_headers, product_id) == 5
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_cancelling_a_reservation_refunds_the_deposit_by_default() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Refund Store", "Main")
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "40.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "30.00"}],
                    "pickup_at": _pickup(),
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()
            assert body["refunded_amount"] == "0.00"

            cancelled = await client.post(f"/api/v1/orders/{body['id']}/cancel", headers=store_headers, json={})
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["status"] == "cancelled"
            assert cancelled.json()["refunded_amount"] == "30.00"
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_store_can_forfeit_the_deposit_on_cancellation() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Forfeit Store", "Main")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            store_id = ctx["store_id"]
            patched = await client.patch(f"/api/v1/stores/{store_id}", headers=headers, json={"preferences": {"reservation_cancel_deposit": "forfeit"}})
            assert patched.status_code == 200, patched.text
            product_id = await _make_product(client, store_headers, "40.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "30.00"}],
                    "pickup_at": _pickup(),
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()

            cancelled = await client.post(f"/api/v1/orders/{body['id']}/cancel", headers=store_headers, json={})
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["status"] == "cancelled"
            assert cancelled.json()["refunded_amount"] == "0.00"

            # Cancelling an already-closed order is refused (guards double refunds).
            again = await client.post(f"/api/v1/orders/{body['id']}/cancel", headers=store_headers, json={})
            assert again.status_code == 409
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_cancel_can_override_the_store_forfeit_policy() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Override Store", "Main")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            store_id = ctx["store_id"]
            patched = await client.patch(f"/api/v1/stores/{store_id}", headers=headers, json={"preferences": {"reservation_cancel_deposit": "forfeit"}})
            assert patched.status_code == 200, patched.text
            product_id = await _make_product(client, store_headers, "40.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "30.00"}],
                    "pickup_at": _pickup(),
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()

            # The store forfeits by default, but the caller can refund explicitly.
            cancelled = await client.post(f"/api/v1/orders/{body['id']}/cancel", headers=store_headers, json={"refund_deposit": True})
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["refunded_amount"] == "30.00"
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_expired_reservation_refunds_the_deposit() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Expiry Refund Store", "Main")
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "30.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 2}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "10.00"}],
                    "pickup_at": _pickup(48),
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()

            async with SessionLocal() as db:
                await db.execute(text("UPDATE orders SET reservation_expires_at = now() - interval '1 hour' WHERE id = :order_id"), {"order_id": uuid.UUID(body["id"])})
                await db.commit()

            assert (await client.get("/api/v1/orders", headers=store_headers)).status_code == 200
            fetched = await client.get(f"/api/v1/orders/{body['id']}", headers=store_headers)
            assert fetched.json()["status"] == "reservation_expired"
            assert fetched.json()["refunded_amount"] == "10.00"
            assert await _on_hand(client, store_headers, product_id) == 5
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_trade_in_credit_settles_a_reservation_balance() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Balance Trade-in Store", "Main", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"service_tax_rate": 0})
            product_id = await _make_product(client, store_headers, "100.00", 5)
            trade_product_id = await _make_product(client, store_headers, "500.00", 0)
            trade_in = (await client.post("/api/v1/trade-ins", headers=store_headers, json={"product_id": trade_product_id, "serial_number": f"TRD-{uuid.uuid4().hex[:8]}", "assessed_value": "30.00"})).json()

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "40.00"}],
                    "pickup_at": _pickup(),
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()
            assert body["balance_due"] == "60.00"
            assert await _on_hand(client, store_headers, product_id) == 4

            collected = await client.post(
                f"/api/v1/orders/{body['id']}/collect",
                headers=store_headers,
                json={"tenders": [
                    {"method": "trade_in", "currency_code": "USD", "amount": "30.00", "trade_in_id": trade_in["id"]},
                    {"method": "cash", "currency_code": "USD", "amount": "30.00"},
                ]},
            )
            assert collected.status_code == 200, collected.text
            assert collected.json()["status"] == "paid"
            assert collected.json()["amount_paid"] == "100.00"
            assert collected.json()["balance_due"] == "0.00"
            applied = (await client.get(f"/api/v1/trade-ins/{trade_in['id']}", headers=store_headers)).json()
            assert applied["order_id"] == body["id"]
            # The held unit is not drawn down a second time on collection.
            assert await _on_hand(client, store_headers, product_id) == 4
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_khqr_settles_a_reservation_balance() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Balance KHQR Store", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            linked = await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": "https://link.payway.com.kh/ABAPAYpe518710Y"})
            assert linked.status_code == 200, linked.text
            assert linked.json()["aba_payway_status"] == "active"
            product_id = await _make_product(client, store_headers, "4.50", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "2.00"}],
                    "pickup_at": _pickup(),
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()
            balance = body["balance_due"]
            assert await _on_hand(client, store_headers, product_id) == 4

            pending = await client.post(
                f"/api/v1/orders/{body['id']}/collect",
                headers=store_headers,
                json={"tenders": [{"method": "khqr", "currency_code": "USD", "amount": balance}]},
            )
            assert pending.status_code == 200, pending.text
            assert pending.json()["status"] == "pending_pickup"
            qr_payment = next(payment for payment in pending.json()["payments"] if payment["provider"] == "chamabapay")
            assert qr_payment["external_id"]

            done = await client.post(f"/api/v1/mock/chamabapay/{qr_payment['external_id']}/complete")
            assert done.status_code == 204, done.text
            after = await client.get(f"/api/v1/orders/{body['id']}", headers=store_headers)
            assert after.json()["status"] == "paid"
            assert after.json()["balance_due"] == "0.00"
            assert await _on_hand(client, store_headers, product_id) == 4
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_reservations_report_summarises_open_pickups() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Reservations Report Store", "Main")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"service_tax_rate": 0})
            product_id = await _make_product(client, store_headers, "100.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "40.00"}],
                    "pickup_at": _pickup(),
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()

            report = await client.get("/api/v1/reports/reservations", headers=store_headers)
            assert report.status_code == 200, report.text
            data = report.json()
            assert data["open_count"] == 1
            assert data["overdue_count"] == 0
            assert data["deposits_held"] == "40.00"
            assert data["balances_due"] == "60.00"
            assert len(data["rows"]) == 1
            row = data["rows"][0]
            assert row["order_id"] == body["id"]
            assert row["balance_due"] == "60.00"
            assert row["overdue"] is False

            # Settling the balance removes it from the open book.
            collected = await client.post(
                f"/api/v1/orders/{body['id']}/collect",
                headers=store_headers,
                json={"tenders": [{"method": "cash", "currency_code": "USD", "amount": "60.00"}]},
            )
            assert collected.status_code == 200, collected.text
            after = (await client.get("/api/v1/reports/reservations", headers=store_headers)).json()
            assert after["open_count"] == 0
            assert after["balances_due"] == "0.00"
    finally:
        await cleanup_company(company_id, [email] if email else [])
