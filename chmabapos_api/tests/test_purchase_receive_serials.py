from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import ProductSerial


async def _setup_store(client: AsyncClient) -> dict[str, str]:
    email = f"po-receive-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "PO Receive Test", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "PO Receive Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    return {**headers, "X-Store-ID": setup.json()["store"]["id"]}


async def _serial_product(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    product = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "PO Laptop", "sku": f"POL-{uuid.uuid4().hex[:8]}", "price": "1500.00", "track_serials": True},
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    variants = await client.put(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"variants": [{"sku": f"POL-512-{uuid.uuid4().hex[:6]}", "name": "512GB"}]},
    )
    assert variants.status_code == 200, variants.text
    return product_id, variants.json()["variants"][0]["id"]


async def _supplier(client: AsyncClient, headers: dict[str, str]) -> str:
    created = await client.post("/api/v1/suppliers", headers=headers, json={"name": "Receive Supplier"})
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def _on_hand(client: AsyncClient, headers: dict[str, str], product_id: str, variant_id: str | None) -> int:
    inventory = (await client.get("/api/v1/inventory", headers=headers)).json()
    row = next(item for item in inventory if item["product_id"] == product_id)
    if variant_id is None:
        return row["on_hand"]
    variant = next(item for item in row["variants"] if item["variant_id"] == variant_id)
    return variant["on_hand"]


@pytest.mark.asyncio
async def test_a_serial_tracked_order_is_received_in_parts() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variant_id = await _serial_product(client, headers)
        supplier_id = await _supplier(client, headers)

        created = await client.post(
            "/api/v1/purchases",
            headers=headers,
            json={"supplier_id": supplier_id, "items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 2, "unit_cost": "900.00"}]},
        )
        assert created.status_code == 201, created.text
        purchase_id = created.json()["id"]
        tag = uuid.uuid4().hex[:8]

        # The first unit arrives with its serial; the order is now partly received.
        first = await client.post(
            f"/api/v1/purchases/{purchase_id}/receive",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 1, "serials": [{"serial_number": f"RCV-{tag}-1"}]}]},
        )
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "partially_received"
        assert await _on_hand(client, headers, product_id, variant_id) == 1

        async with SessionLocal() as db:
            serial = (
                await db.execute(
                    select(ProductSerial).where(
                        ProductSerial.serial_number == f"RCV-{tag}-1",
                        ProductSerial.store_id == uuid.UUID(headers["X-Store-ID"]),
                    )
                )
            ).scalar_one()
            # The unit is traced back to the order and the supplier that sent it.
            assert str(serial.purchase_order_id) == purchase_id
            assert str(serial.supplier_id) == supplier_id
            assert str(serial.cost_price) == "900.00"
            assert str(serial.store_id) == headers["X-Store-ID"]

        # The second unit completes the order.
        second = await client.post(
            f"/api/v1/purchases/{purchase_id}/receive",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 1, "serials": [{"serial_number": f"RCV-{tag}-2"}]}]},
        )
        assert second.status_code == 200, second.text
        assert second.json()["status"] == "received"
        assert await _on_hand(client, headers, product_id, variant_id) == 2

        # Nothing is left, so the order cannot be received again.
        again = await client.post(
            f"/api/v1/purchases/{purchase_id}/receive",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 1, "serials": [{"serial_number": f"RCV-{tag}-3"}]}]},
        )
        assert again.status_code == 409, again.text


@pytest.mark.asyncio
async def test_receiving_more_than_was_ordered_is_rejected() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variant_id = await _serial_product(client, headers)
        created = await client.post(
            "/api/v1/purchases",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 1, "unit_cost": "900.00"}]},
        )
        assert created.status_code == 201, created.text
        too_many = await client.post(
            f"/api/v1/purchases/{created.json()['id']}/receive",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 2, "serials": [{"serial_number": "X-1"}, {"serial_number": "X-2"}]}]},
        )
        assert too_many.status_code == 400, too_many.text
        # Nothing was received, so the order is still open.
        listed = (await client.get("/api/v1/purchases", headers=headers)).json()
        assert next(row for row in listed if row["id"] == created.json()["id"])["status"] == "ordered"


@pytest.mark.asyncio
async def test_a_serial_line_without_serials_is_explained() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variant_id = await _serial_product(client, headers)
        created = await client.post(
            "/api/v1/purchases",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 1}]},
        )
        assert created.status_code == 201, created.text
        # A client that sends no body at all (the Android till) is told what to
        # send rather than silently breaking the one-serial-per-unit invariant.
        blank = await client.post(f"/api/v1/purchases/{created.json()['id']}/receive", headers=headers)
        assert blank.status_code == 400, blank.text
        assert "one serial per unit" in blank.json()["detail"]


@pytest.mark.asyncio
async def test_a_plain_product_can_still_be_received_in_parts() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product = await client.post("/api/v1/products", headers=headers, json={"name": "PO Cable", "sku": f"POC-{uuid.uuid4().hex[:8]}", "price": "5.00"})
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]
        created = await client.post(
            "/api/v1/purchases",
            headers=headers,
            json={"items": [{"product_id": product_id, "quantity": 5, "unit_cost": "2.00"}]},
        )
        assert created.status_code == 201, created.text
        purchase_id = created.json()["id"]

        part = await client.post(
            f"/api/v1/purchases/{purchase_id}/receive",
            headers=headers,
            json={"items": [{"product_id": product_id, "quantity": 2}]},
        )
        assert part.status_code == 200, part.text
        assert part.json()["status"] == "partially_received"
        assert await _on_hand(client, headers, product_id, None) == 2

        rest = await client.post(f"/api/v1/purchases/{purchase_id}/receive", headers=headers)
        assert rest.status_code == 200, rest.text
        assert rest.json()["status"] == "received"
        assert await _on_hand(client, headers, product_id, None) == 5
        # The ordered unit cost rides on the movement, so COGS is not blank.
        movement_cost = rest.json()["items"][0]["unit_cost"]
        assert movement_cost == "2.00"

@pytest.mark.asyncio
async def test_a_partly_received_order_can_be_cancelled_without_losing_stock() -> None:
    """A short shipment must be closable.

    Before this, an order was only cancellable while nothing had arrived, so a
    supplier who sent 1 of 3 units left an order that could be neither received
    in full nor cancelled. Cancelling closes the remainder; the units already
    received stay in stock and stay linked to the order.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _setup_store(client)
        product_id, variant_id = await _serial_product(client, headers)
        created = await client.post(
            "/api/v1/purchases",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 3, "unit_cost": "700.00"}]},
        )
        assert created.status_code == 201, created.text
        purchase_id = created.json()["id"]
        tag = uuid.uuid4().hex[:8]

        partial = await client.post(
            f"/api/v1/purchases/{purchase_id}/receive",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 1, "serials": [{"serial_number": f"CNL-{tag}-1"}]}]},
        )
        assert partial.status_code == 200, partial.text
        assert partial.json()["status"] == "partially_received"

        cancelled = await client.post(f"/api/v1/purchases/{purchase_id}/cancel", headers=headers)
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "cancelled"

        # The unit that did arrive is still on the shelf, still tied to the order.
        assert await _on_hand(client, headers, product_id, variant_id) == 1
        async with SessionLocal() as db:
            serial = (
                await db.execute(
                    select(ProductSerial).where(
                        ProductSerial.serial_number == f"CNL-{tag}-1",
                        ProductSerial.store_id == uuid.UUID(headers["X-Store-ID"]),
                    )
                )
            ).scalar_one()
            assert str(serial.purchase_order_id) == purchase_id

        # A cancelled order accepts nothing more.
        blocked = await client.post(
            f"/api/v1/purchases/{purchase_id}/receive",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 2, "serials": [{"serial_number": f"CNL-{tag}-2"}, {"serial_number": f"CNL-{tag}-3"}]}]},
        )
        assert blocked.status_code == 409, blocked.text
