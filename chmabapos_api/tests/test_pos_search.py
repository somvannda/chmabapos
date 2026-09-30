from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _owner_with_two_stores(client: AsyncClient) -> tuple[dict[str, str], dict[str, str]]:
    """Register an owner, open a paid pro workspace and add a second store."""
    email = f"pos-search-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "POS Search", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "POS Search Co", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "pro"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete")
    store_one = setup.json()["store"]["id"]
    second = await client.post("/api/v1/stores", headers=headers, json={"name": "Branch Two", "currency_code": "USD", "timezone": "Asia/Phnom_Penh"})
    assert second.status_code == 201, second.text
    return {**headers, "X-Store-ID": store_one}, {**headers, "X-Store-ID": second.json()["id"]}


async def _serial_variant_product(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str, str, str]:
    """A serial-tracked, branded product with one variant; returns (product_id, variant_id, barcode, brand)."""
    barcode = f"BC-{uuid.uuid4().hex[:10]}"
    brand = f"Brand-{uuid.uuid4().hex[:6]}"
    product = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Search Laptop", "sku": f"SL-{uuid.uuid4().hex[:8]}", "price": "900.00", "track_serials": True, "barcode": barcode, "brand": brand},
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    variants = await client.put(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"variants": [{"sku": f"SGA-{uuid.uuid4().hex[:6]}", "name": "Space Gray"}]},
    )
    assert variants.status_code == 200, variants.text
    variant_id = variants.json()["variants"][0]["id"]
    return product_id, variant_id, barcode, brand


async def _add_serial(client: AsyncClient, headers: dict[str, str], product_id: str, variant_id: str, serial_number: str) -> None:
    added = await client.post(
        f"/api/v1/products/{product_id}/serials",
        headers=headers,
        json={"serials": [{"serial_number": serial_number, "variant_id": variant_id, "cost_price": "700.00", "supplier_warranty_months": 12, "condition_grade": "good", "battery_health": 88, "battery_cycle_count": 210}]},
    )
    assert added.status_code == 201, added.text


@pytest.mark.asyncio
async def test_pos_search_matches_serial_barcode_brand_and_hides_cost() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        store_one, _ = await _owner_with_two_stores(client)
        product_id, variant_id, barcode, brand = await _serial_variant_product(client, store_one)
        serial = f"SN-{uuid.uuid4().hex[:10]}"
        await _add_serial(client, store_one, product_id, variant_id, serial)

        by_serial = await client.get(f"/api/v1/pos/search?q={serial}", headers=store_one)
        assert by_serial.status_code == 200, by_serial.text
        hits = by_serial.json()["serials"]
        assert len(hits) == 1
        hit = hits[0]
        assert hit["serial_number"] == serial
        assert hit["product_id"] == product_id
        assert hit["variant_id"] == variant_id
        assert hit["variant_name"] == "Space Gray"
        assert hit["product_name"] == "Search Laptop"
        # Cosmetic condition travels with the hit so the cashier can pick a unit.
        assert hit["condition_grade"] == "good"
        assert hit["battery_health"] == 88
        assert hit["battery_cycle_count"] == 210
        # The till payload must never leak cost, supplier or warranty data.
        for leaked in ("cost_price", "supplier_warranty_months", "customer_warranty_months", "supplier_id", "supplier_name", "sold_at"):
            assert leaked not in hit

        by_barcode = await client.get(f"/api/v1/pos/search?q={barcode}", headers=store_one)
        assert by_barcode.status_code == 200, by_barcode.text
        assert any(row["barcode"] == barcode for row in by_barcode.json()["products"])

        by_brand = await client.get(f"/api/v1/pos/search?q={brand}", headers=store_one)
        assert by_brand.status_code == 200, by_brand.text
        assert any(row["product_id"] == product_id for row in by_brand.json()["products"])


@pytest.mark.asyncio
async def test_pos_search_is_store_scoped_and_excludes_sold_units() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        store_one, store_two = await _owner_with_two_stores(client)
        product_id, variant_id, _, _ = await _serial_variant_product(client, store_one)
        here = f"SN-HERE-{uuid.uuid4().hex[:8]}"
        there = f"SN-THERE-{uuid.uuid4().hex[:8]}"
        await _add_serial(client, store_one, product_id, variant_id, here)
        await _add_serial(client, store_one, product_id, variant_id, there)

        moved = await client.post(
            "/api/v1/inventory/transfers",
            headers=store_one,
            json={"to_store_id": store_two["X-Store-ID"], "items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 1, "serial_numbers": [there]}]},
        )
        assert moved.status_code == 200, moved.text

        # A serial sitting at branch two must not surface at branch one, and vice versa.
        assert (await client.get(f"/api/v1/pos/search?q={there}", headers=store_one)).json()["serials"] == []
        assert [row["serial_number"] for row in (await client.get(f"/api/v1/pos/search?q={there}", headers=store_two)).json()["serials"]] == [there]
        assert [row["serial_number"] for row in (await client.get(f"/api/v1/pos/search?q={here}", headers=store_one)).json()["serials"]] == [here]

        sale = await client.post(
            "/api/v1/orders",
            headers=store_one,
            json={"items": [{"product_id": product_id, "variant_id": variant_id, "quantity": 1, "serial_numbers": [here]}], "payment_method": "cash"},
        )
        assert sale.status_code == 201, sale.text

        # Sold units are no longer sellable, so they drop out of the till search.
        assert (await client.get(f"/api/v1/pos/search?q={here}", headers=store_one)).json()["serials"] == []
