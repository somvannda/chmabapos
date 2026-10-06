from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup

pytestmark = pytest.mark.asyncio

ABA_LINK = "https://link.payway.com.kh/ABAPAYpe518710Y"


async def _make_product(client: AsyncClient, store_headers: dict[str, str], price: str, opening_stock: int) -> str:
    product = await client.post(
        "/api/v1/products",
        headers=store_headers,
        json={"name": f"Split {uuid.uuid4().hex[:6]}", "sku": f"SP-{uuid.uuid4().hex[:8]}", "price": price, "opening_stock": opening_stock},
    )
    assert product.status_code == 201, product.text
    return product.json()["id"]


async def _enable_khqr(client: AsyncClient, headers: dict[str, str]) -> None:
    linked = await client.patch("/api/v1/company", headers=headers, json={"aba_payway_link": ABA_LINK})
    assert linked.status_code == 200, linked.text
    assert linked.json()["aba_payway_status"] == "active"


def _pending_qr(order: dict) -> dict:
    return next(payment for payment in order["payments"] if payment["status"] != "paid" and payment["external_id"])


async def _on_hand(client: AsyncClient, store_headers: dict[str, str], product_id: str) -> float:
    products = (await client.get("/api/v1/products", headers=store_headers)).json()
    return next(product["on_hand"] for product in products if product["id"] == product_id)


def _pickup(offset_hours: int = 24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=offset_hours)).isoformat()


async def test_checkout_accepts_split_cash_and_khqr() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Split Checkout Store", "Main Counter", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            await _enable_khqr(client, ctx["headers"])
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "100.00", 5)

            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [
                        {"method": "cash", "currency_code": "USD", "amount": "40.00"},
                        {"method": "khqr", "currency_code": "USD", "amount": "70.00"},
                    ],
                },
            )
            assert order.status_code == 201, order.text
            body = order.json()
            # Cash is taken now, the QR settles later, so the order stays open.
            assert body["status"] == "payment_pending"
            assert float(body["total"]) == 110.0
            assert float(body["amount_paid"]) == 40.0
            assert float(body["balance_due"]) == 70.0
            # Stock is not drawn down until the order completes.
            assert await _on_hand(client, store_headers, product_id) == 5

            qr = _pending_qr(body)
            assert float(qr["amount"]) == 70.0

            completed = await client.post(f"/api/v1/mock/chamabapay/{qr['external_id']}/complete")
            assert completed.status_code == 204, completed.text

            after = await client.get(f"/api/v1/orders/{body['id']}", headers=store_headers)
            assert after.status_code == 200, after.text
            paid = after.json()
            assert paid["status"] == "paid"
            assert float(paid["balance_due"]) == 0.0
            assert paid["paid_at"] is not None
            assert await _on_hand(client, store_headers, product_id) == 4
    finally:
        await cleanup_company(company_id, [email] if email else [])


async def test_checkout_accepts_full_khqr_deposit() -> None:
    """A reservation deposit can be paid entirely by KHQR and opens for pickup."""
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "KHQR Deposit Store", "Main Counter", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            await _enable_khqr(client, ctx["headers"])
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "100.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "khqr", "currency_code": "USD", "amount": "30.00"}],
                    "pickup_at": _pickup(),
                    "hold_stock": True,
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()
            # The deposit QR is still pending, so the reservation has not opened.
            assert body["status"] == "payment_pending"
            assert float(body["total"]) == 110.0
            assert float(body["deposit"]) == 30.0
            assert float(body["amount_paid"]) == 0.0
            # Held stock is drawn down as soon as the reservation is taken.
            assert await _on_hand(client, store_headers, product_id) == 4

            qr = _pending_qr(body)
            assert float(qr["amount"]) == 30.0

            completed = await client.post(f"/api/v1/mock/chamabapay/{qr['external_id']}/complete")
            assert completed.status_code == 204, completed.text

            after = await client.get(f"/api/v1/orders/{body['id']}", headers=store_headers)
            assert after.status_code == 200, after.text
            reserved = after.json()
            assert reserved["status"] == "pending_pickup"
            assert float(reserved["amount_paid"]) == 30.0
            assert float(reserved["balance_due"]) == 80.0
            assert reserved["reservation_expires_at"] is not None

            collected = await client.post(
                f"/api/v1/orders/{body['id']}/collect",
                headers=store_headers,
                json={"tenders": [{"method": "cash", "currency_code": "USD", "amount": "80.00"}]},
            )
            assert collected.status_code == 200, collected.text
            paid = collected.json()
            assert paid["status"] == "paid"
            assert float(paid["balance_due"]) == 0.0
            # Held stock was drawn down once at deposit time, not again at pickup.
            assert await _on_hand(client, store_headers, product_id) == 4
    finally:
        await cleanup_company(company_id, [email] if email else [])


async def test_checkout_accepts_split_cash_and_khqr_deposit() -> None:
    """A deposit can be split: cash now, the rest by a KHQR that settles later."""
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Split Deposit Store", "Main Counter", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            await _enable_khqr(client, ctx["headers"])
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "100.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [
                        {"method": "cash", "currency_code": "USD", "amount": "10.00"},
                        {"method": "khqr", "currency_code": "USD", "amount": "20.00"},
                    ],
                    "pickup_at": _pickup(),
                    "hold_stock": True,
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()
            assert body["status"] == "payment_pending"
            assert float(body["deposit"]) == 30.0
            assert float(body["amount_paid"]) == 10.0
            assert float(body["balance_due"]) == 100.0
            assert await _on_hand(client, store_headers, product_id) == 4

            qr = _pending_qr(body)
            assert float(qr["amount"]) == 20.0

            completed = await client.post(f"/api/v1/mock/chamabapay/{qr['external_id']}/complete")
            assert completed.status_code == 204, completed.text

            after = await client.get(f"/api/v1/orders/{body['id']}", headers=store_headers)
            assert after.status_code == 200, after.text
            reserved = after.json()
            assert reserved["status"] == "pending_pickup"
            assert float(reserved["amount_paid"]) == 30.0
            assert float(reserved["balance_due"]) == 80.0
    finally:
        await cleanup_company(company_id, [email] if email else [])


async def test_stale_khqr_deposit_expires_and_releases_stock() -> None:
    """A deposit QR that never settles is swept, releasing the held stock."""
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Stale Deposit Store", "Main Counter", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            await _enable_khqr(client, ctx["headers"])
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "100.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "khqr", "currency_code": "USD", "amount": "30.00"}],
                    "pickup_at": _pickup(),
                    "hold_stock": True,
                },
            )
            assert reservation.status_code == 201, reservation.text
            body = reservation.json()
            assert body["status"] == "payment_pending"
            assert await _on_hand(client, store_headers, product_id) == 4

            # Pretend the QR window lapsed without a settlement.
            stale_at = datetime.now(timezone.utc) - timedelta(minutes=30)
            async with SessionLocal() as db:
                await db.execute(text("UPDATE orders SET created_at = :ts WHERE id = :oid"), {"ts": stale_at, "oid": body["id"]})
                await db.commit()

            listed = await client.get("/api/v1/orders", headers=store_headers)
            assert listed.status_code == 200, listed.text

            after = await client.get(f"/api/v1/orders/{body['id']}", headers=store_headers)
            assert after.status_code == 200, after.text
            stale = after.json()
            assert stale["status"] == "payment_expired"
            assert await _on_hand(client, store_headers, product_id) == 5
    finally:
        await cleanup_company(company_id, [email] if email else [])


async def test_checkout_rejects_khqr_that_does_not_cover_the_balance() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Split Reject Store", "Main Counter", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            await _enable_khqr(client, ctx["headers"])
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "100.00", 5)

            short = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [
                        {"method": "cash", "currency_code": "USD", "amount": "40.00"},
                        {"method": "khqr", "currency_code": "USD", "amount": "60.00"},
                    ],
                },
            )
            assert short.status_code == 400, short.text
            assert "KHQR must cover the remaining 70.00" in short.json()["detail"]

            double = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [
                        {"method": "khqr", "currency_code": "USD", "amount": "70.00"},
                        {"method": "khqr", "currency_code": "USD", "amount": "40.00"},
                    ],
                },
            )
            assert double.status_code == 400, double.text
            assert "at most one KHQR" in double.json()["detail"]

            # A rejected order never holds stock.
            assert await _on_hand(client, store_headers, product_id) == 5
    finally:
        await cleanup_company(company_id, [email] if email else [])


async def test_collect_balance_accepts_split_cash_and_khqr() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Split Collect Store", "Main Counter", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            await _enable_khqr(client, ctx["headers"])
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "100.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "30.00"}],
                    "pickup_at": _pickup(),
                    "hold_stock": True,
                },
            )
            assert reservation.status_code == 201, reservation.text
            reserved = reservation.json()
            assert reserved["status"] == "pending_pickup"
            assert float(reserved["balance_due"]) == 80.0
            assert await _on_hand(client, store_headers, product_id) == 4

            collected = await client.post(
                f"/api/v1/orders/{reserved['id']}/collect",
                headers=store_headers,
                json={
                    "tenders": [
                        {"method": "cash", "currency_code": "USD", "amount": "20.00"},
                        {"method": "khqr", "currency_code": "USD", "amount": "60.00"},
                    ]
                },
            )
            assert collected.status_code == 200, collected.text
            body = collected.json()
            # Deposit 30 + cash 20 is settled; the QR 60 is still outstanding.
            assert body["status"] == "pending_pickup"
            assert float(body["amount_paid"]) == 50.0
            assert float(body["balance_due"]) == 60.0

            qr = _pending_qr(body)
            assert float(qr["amount"]) == 60.0

            completed = await client.post(f"/api/v1/mock/chamabapay/{qr['external_id']}/complete")
            assert completed.status_code == 204, completed.text

            after = await client.get(f"/api/v1/orders/{reserved['id']}", headers=store_headers)
            assert after.status_code == 200, after.text
            paid = after.json()
            assert paid["status"] == "paid"
            assert float(paid["balance_due"]) == 0.0
            # Held stock was drawn down once at deposit time, not again at pickup.
            assert await _on_hand(client, store_headers, product_id) == 4
    finally:
        await cleanup_company(company_id, [email] if email else [])


async def test_pickup_order_receipt_email_shows_deposit_and_balance(monkeypatch) -> None:
    email: str | None = None
    company_id: str | None = None
    captured: dict = {}

    async def fake_send(recipient, subject, text, html=None):
        captured["recipient"] = recipient
        captured["subject"] = subject
        captured["html"] = html or text
        return True

    monkeypatch.setattr("app.api.v1.send_email", fake_send)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Pickup Receipt Store", "Main Counter", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            customer = await client.post("/api/v1/customers", headers=headers, json={"name": "Chan Meas", "phone": "+855 10 000 111", "email": "chan-receipt@example.com"})
            assert customer.status_code == 201, customer.text
            customer_id = customer.json()["id"]
            product_id = await _make_product(client, store_headers, "100.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "30.00"}],
                    "pickup_at": _pickup(),
                    "customer_id": customer_id,
                },
            )
            assert reservation.status_code == 201, reservation.text
            assert reservation.json()["status"] == "pending_pickup"

            sent = await client.post(f"/api/v1/orders/{reservation.json()['id']}/email-receipt", headers=store_headers)
            assert sent.status_code == 200, sent.text
            assert sent.json()["email"] == "chan-receipt@example.com"
            assert captured["recipient"] == "chan-receipt@example.com"
            assert "Deposit paid" in captured["html"]
            assert "Balance due" in captured["html"]
            assert "Pickup" in captured["html"]
            # The email is labelled as a deposit receipt, mirroring the printed one.
            assert "Deposit receipt" in captured["html"]
            assert "deposit receipt" in captured["subject"].lower()
    finally:
        await cleanup_company(company_id, [email] if email else [])


async def test_reschedule_pending_pickup_updates_window() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Reschedule Store", "Main Counter")
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "100.00", 5)

            reservation = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={
                    "items": [{"product_id": product_id, "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "30.00"}],
                    "pickup_at": _pickup(24),
                },
            )
            assert reservation.status_code == 201, reservation.text
            order_id = reservation.json()["id"]

            new_pickup = datetime.now(timezone.utc) + timedelta(hours=72)
            patched = await client.patch(f"/api/v1/orders/{order_id}/pickup", headers=store_headers, json={"pickup_at": new_pickup.isoformat(), "pickup_note": "rescheduled"})
            assert patched.status_code == 200, patched.text
            updated = patched.json()
            assert updated["pickup_note"] == "rescheduled"
            got = datetime.fromisoformat(updated["pickup_at"].replace("Z", "+00:00"))
            assert abs((got - new_pickup).total_seconds()) < 1
            expires = datetime.fromisoformat(updated["reservation_expires_at"].replace("Z", "+00:00"))
            assert abs((expires - new_pickup).total_seconds() - 24 * 3600) < 5

            # A completed sale is not a reservation and cannot be rescheduled.
            sale = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"})
            assert sale.status_code == 201 and sale.json()["status"] == "paid"
            refused = await client.patch(f"/api/v1/orders/{sale.json()['id']}/pickup", headers=store_headers, json={"pickup_at": new_pickup.isoformat()})
            assert refused.status_code == 409
    finally:
        await cleanup_company(company_id, [email] if email else [])


async def test_reservations_report_flags_failed_balance_qr() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Report Retry Store", "Main Counter", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            await _enable_khqr(client, ctx["headers"])
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "100.00", 5)

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
            reserved = reservation.json()
            balance = f"{float(reserved['balance_due']):.2f}"

            # Raise a balance QR, then let it fail the way the provider would.
            collected = await client.post(f"/api/v1/orders/{reserved['id']}/collect", headers=store_headers, json={"tenders": [{"method": "khqr", "currency_code": "USD", "amount": balance}]})
            assert collected.status_code == 200, collected.text

            async with SessionLocal() as db:
                await db.execute(text("UPDATE payments SET status = 'expired' WHERE order_id = :oid AND external_id IS NOT NULL"), {"oid": reserved["id"]})
                await db.commit()

            report = await client.get("/api/v1/reports/reservations", headers=store_headers)
            assert report.status_code == 200, report.text
            row = next(entry for entry in report.json()["rows"] if entry["order_id"] == reserved["id"])
            assert row["payment_failed"] is True
    finally:
        await cleanup_company(company_id, [email] if email else [])


async def test_collect_balance_does_not_issue_a_second_qr() -> None:
    """A retried collect must re-use the open balance QR, never double it."""
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Collect Guard Store", "Main Counter", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            await _enable_khqr(client, ctx["headers"])
            store_headers = ctx["store_headers"]
            product_id = await _make_product(client, store_headers, "100.00", 5)

            reserved = (
                await client.post(
                    "/api/v1/orders",
                    headers=store_headers,
                    json={"items": [{"product_id": product_id, "quantity": 1}], "tenders": [{"method": "cash", "currency_code": "USD", "amount": "30.00"}], "pickup_at": _pickup(), "hold_stock": True},
                )
            ).json()
            assert reserved["status"] == "pending_pickup"
            assert float(reserved["balance_due"]) == 80.0

            first = await client.post(f"/api/v1/orders/{reserved['id']}/collect", headers=store_headers, json={"tenders": [{"method": "khqr", "currency_code": "USD", "amount": "80.00"}]})
            assert first.status_code == 200, first.text
            qr = _pending_qr(first.json())

            # Retrying the collect re-uses the open QR instead of creating another.
            second = await client.post(f"/api/v1/orders/{reserved['id']}/collect", headers=store_headers, json={"tenders": [{"method": "khqr", "currency_code": "USD", "amount": "80.00"}]})
            assert second.status_code == 200, second.text
            pending = [payment for payment in second.json()["payments"] if payment["status"] in {"pending", "scanned"}]
            assert len(pending) == 1
            assert pending[0]["id"] == qr["id"]

            # Collecting cash while a balance QR is pending would double-collect.
            blocked = await client.post(f"/api/v1/orders/{reserved['id']}/collect", headers=store_headers, json={"tenders": [{"method": "cash", "currency_code": "USD", "amount": "80.00"}]})
            assert blocked.status_code == 409, blocked.text

            completed = await client.post(f"/api/v1/mock/chamabapay/{qr['external_id']}/complete")
            assert completed.status_code == 204, completed.text
            after = await client.get(f"/api/v1/orders/{reserved['id']}", headers=store_headers)
            assert after.json()["status"] == "paid"
            assert float(after.json()["balance_due"]) == 0.0
    finally:
        await cleanup_company(company_id, [email] if email else [])
