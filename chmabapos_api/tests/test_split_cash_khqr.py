from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

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
