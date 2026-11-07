from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def _setup_store(client: AsyncClient) -> tuple[dict[str, str], str]:
    """Register an owner, verify, sign in and open a paid starter workspace."""
    email = f"serial-truth-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Serial Truth Test", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Serial Truth Store", "store_name": "Main", "country": "Cambodia", "currency_code": "USD", "plan_code": "starter"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete", headers=headers)
    return {**headers, "X-Store-ID": setup.json()["store"]["id"]}, setup.json()["store"]["id"]


async def _inventory_row(client: AsyncClient, headers: dict[str, str], product_id: str) -> dict:
    inventory = await client.get("/api/v1/inventory", headers=headers)
    assert inventory.status_code == 200, inventory.text
    return next(row for row in inventory.json() if row["product_id"] == product_id)


async def _catalog_row(client: AsyncClient, headers: dict[str, str], product_id: str) -> dict:
    catalog = await client.get("/api/v1/products", headers=headers)
    assert catalog.status_code == 200, catalog.text
    return next(row for row in catalog.json() if row["id"] == product_id)


@pytest.mark.asyncio
async def test_serial_units_are_the_stock_and_balances_cannot_disagree() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, store_id = await _setup_store(client)

        # A tracked product cannot start with anonymous stock.
        rejected = await client.post("/api/v1/products", headers=headers, json={"name": "Ghost Stock", "sku": f"GH-{uuid.uuid4().hex[:8]}", "price": "10.00", "track_serials": True, "opening_stock": 5})
        assert rejected.status_code == 400, rejected.text

        product = await client.post("/api/v1/products", headers=headers, json={"name": "Truth Laptop", "sku": f"TR-{uuid.uuid4().hex[:8]}", "price": "100.00", "track_serials": True})
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]
        assert product.json()["on_hand"] == 0

        # A variant cannot carry opening stock either.
        bad_variant = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [{"sku": f"TR-A-{uuid.uuid4().hex[:6]}", "name": "128GB", "opening_stock": 2}]},
        )
        assert bad_variant.status_code == 400, bad_variant.text

        variants = await client.put(
            f"/api/v1/products/{product_id}/variants",
            headers=headers,
            json={"variants": [
                {"sku": f"TR-A-{uuid.uuid4().hex[:6]}", "name": "128GB"},
                {"sku": f"TR-B-{uuid.uuid4().hex[:6]}", "name": "256GB"},
            ]},
        )
        assert variants.status_code == 200, variants.text
        variant_a = next(row for row in variants.json()["variants"] if row["name"] == "128GB")["id"]
        variant_b = next(row for row in variants.json()["variants"] if row["name"] == "256GB")["id"]

        # Direct balance edits are refused for a serial-tracked product.
        adjust = await client.patch(f"/api/v1/inventory/{product_id}", headers=headers, json={"quantity": 7, "reason": "count"})
        assert adjust.status_code == 400, adjust.text

        # Receiving without a variant would put units where the variant list cannot see them.
        no_variant = await client.post(f"/api/v1/inventory/{product_id}/restock", headers=headers, json={"quantity": 1, "serial_numbers": ["NO-VARIANT"]})
        assert no_variant.status_code == 400, no_variant.text

        serials_a = [f"TRA-{uuid.uuid4().hex[:8]}" for _ in range(3)]
        serials_b = [f"TRB-{uuid.uuid4().hex[:8]}" for _ in range(2)]
        received_a = await client.post(f"/api/v1/inventory/{product_id}/restock", headers=headers, json={"quantity": 3, "variant_id": variant_a, "serial_numbers": serials_a})
        assert received_a.status_code == 200, received_a.text
        received_b = await client.post(f"/api/v1/inventory/{product_id}/restock", headers=headers, json={"quantity": 2, "variant_id": variant_b, "serial_numbers": serials_b})
        assert received_b.status_code == 200, received_b.text

        catalog_row = await _catalog_row(client, headers, product_id)
        assert {row["name"]: row["on_hand"] for row in catalog_row["variants"]} == {"128GB": 3, "256GB": 2}

        inventory_row = await _inventory_row(client, headers, product_id)
        assert {row["name"]: row["on_hand"] for row in inventory_row["variants"]} == {"128GB": 3, "256GB": 2}
        # Variant stock lives on the variants, not the product row.
        assert inventory_row["on_hand"] == 0

        # The till reports the same unit counts.
        search = await client.get(f"/api/v1/pos/search?q={catalog_row['sku']}", headers=headers)
        assert search.status_code == 200, search.text
        hits = {row["variant_id"]: row["stock"] for row in search.json()["products"] if row["product_id"] == product_id}
        assert hits == {variant_a: 3.0, variant_b: 2.0}, hits

        # A legacy balance that disagrees with the units must not leak to readers.
        async with SessionLocal() as db:
            await db.execute(
                text("UPDATE variant_inventory_balances SET on_hand = 9 WHERE store_id = :store_id AND variant_id = :variant_id"),
                {"store_id": store_id, "variant_id": variant_a},
            )
            await db.commit()
        assert next(row for row in (await _catalog_row(client, headers, product_id))["variants"] if row["id"] == variant_a)["on_hand"] == 3
        assert next(row for row in (await _inventory_row(client, headers, product_id))["variants"] if row["variant_id"] == variant_a)["on_hand"] == 3

        # Even the opposite drift (balance below the units) must not block a sale.
        async with SessionLocal() as db:
            await db.execute(
                text("UPDATE variant_inventory_balances SET on_hand = 0 WHERE store_id = :store_id AND variant_id = :variant_id"),
                {"store_id": store_id, "variant_id": variant_a},
            )
            await db.commit()
        sale = await client.post(
            "/api/v1/orders",
            headers=headers,
            json={"items": [{"product_id": product_id, "variant_id": variant_a, "quantity": 1, "serial_numbers": [serials_a[0]]}], "payment_method": "cash"},
        )
        assert sale.status_code == 201, sale.text
        assert next(row for row in (await _inventory_row(client, headers, product_id))["variants"] if row["variant_id"] == variant_a)["on_hand"] == 2

        # The serial list is scoped to the shelf it is opened from.
        listed = await client.get(f"/api/v1/products/{product_id}/serials", headers=headers, params={"store_id": store_id})
        assert listed.status_code == 200, listed.text
        assert len(listed.json()) == 5
        assert all(row["store_id"] == store_id for row in listed.json())


@pytest.mark.asyncio
async def test_serial_tracking_cannot_be_enabled_over_unsynced_stock() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers, _store_id = await _setup_store(client)

        product = await client.post("/api/v1/products", headers=headers, json={"name": "Late Serial", "sku": f"LS-{uuid.uuid4().hex[:8]}", "price": "10.00", "opening_stock": 4})
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]

        blocked = await client.patch(f"/api/v1/products/{product_id}", headers=headers, json={"track_serials": True})
        assert blocked.status_code == 400, blocked.text

        # Once the shelf is empty there is nothing unsynced to hide.
        zeroed = await client.patch(f"/api/v1/inventory/{product_id}", headers=headers, json={"quantity": 0, "reason": "before serials"})
        assert zeroed.status_code == 200, zeroed.text
        enabled = await client.patch(f"/api/v1/products/{product_id}", headers=headers, json={"track_serials": True})
        assert enabled.status_code == 200, enabled.text
        assert enabled.json()["track_serials"] is True
