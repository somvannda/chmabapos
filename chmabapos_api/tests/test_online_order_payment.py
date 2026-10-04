from __future__ import annotations

import uuid
from datetime import datetime, timezone

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

        event = {
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "payment.paid",
            "created": datetime.now(timezone.utc).isoformat(),
            "data": {"payment": {"id": external_id, "status": "paid", "amount": "3.00", "currency": "USD", "reference_id": "online-test", "approved_at": datetime.now(timezone.utc).isoformat()}},
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
        event = {"id": f"evt_{uuid.uuid4().hex}", "type": "payment.paid", "created": datetime.now(timezone.utc).isoformat(), "data": {"payment": {"id": external_id, "status": "paid", "amount": "3.00", "currency": "USD", "reference_id": "online-test", "approved_at": datetime.now(timezone.utc).isoformat()}}}
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
