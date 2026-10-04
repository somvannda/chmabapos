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
