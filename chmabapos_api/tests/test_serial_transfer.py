from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _two_store_setup(client: AsyncClient) -> tuple[dict[str, str], dict[str, str]]:
    """Register an owner, open a paid pro workspace and add a second store."""
    email = f"serial-transfer-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Serial Transfer", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Serial Transfer Co", "store_name": "Branch One", "country": "Cambodia", "currency_code": "USD", "plan_code": "pro"},
    )
    assert setup.status_code == 201, setup.text
    await client.post(f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete")
    s1 = setup.json()["store"]["id"]
    second = await client.post("/api/v1/stores", headers=headers, json={"name": "Branch Two", "currency_code": "USD", "timezone": "Asia/Phnom_Penh"})
    assert second.status_code == 201, second.text
    return {**headers, "X-Store-ID": s1}, {**headers, "X-Store-ID": second.json()["id"]}


async def _serial_variant_product(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    """A serial-tracked product with a Space Gray variant; returns (product_id, variant_id)."""
    product = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Serial Laptop", "sku": f"SL-{uuid.uuid4().hex[:8]}", "price": "900.00", "track_serials": True},
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    variants = await client.put(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"variants": [
            {"sku": f"SGA-{uuid.uuid4().hex[:6]}", "name": "Space Gray"},
            {"sku": f"SGB-{uuid.uuid4().hex[:6]}", "name": "Rose Gold"},
        ]},
    )
    assert variants.status_code == 200, variants.text
    space_gray = next(row for row in variants.json()["variants"] if row["name"] == "Space Gray")["id"]
    return product_id, space_gray


async def _on_hand(client: AsyncClient, headers: dict[str, str], product_id: str, variant_id: str) -> float:
    rows = await client.get("/api/v1/inventory", headers=headers)
    assert rows.status_code == 200, rows.text
    row = next(item for item in rows.json() if item["product_id"] == product_id)
    return next(variant["on_hand"] for variant in row["variants"] if variant["variant_id"] == variant_id)


@pytest.mark.asyncio
async def test_serial_transfer_reassigns_serials_and_balances() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        s1, s2 = await _two_store_setup(client)
        product_id, space_gray = await _serial_variant_product(client, s1)
        serials = [f"SN-{uuid.uuid4().hex[:8]}" for _ in range(3)]
        added = await client.post(
            f"/api/v1/products/{product_id}/serials",
            headers=s1,
            json={"serials": [{"serial_number": value, "variant_id": space_gray} for value in serials]},
        )
        assert added.status_code == 201, added.text

        transfer = await client.post(
            "/api/v1/inventory/transfers",
            headers=s1,
            json={"to_store_id": s2["X-Store-ID"], "note": "send two to branch two", "items": [
                {"product_id": product_id, "variant_id": space_gray, "quantity": 2, "serial_numbers": serials[:2]},
            ]},
        )
        assert transfer.status_code == 200, transfer.text
        assert sorted(transfer.json()["items"][0]["serials"]) == sorted(serials[:2])

        listed = (await client.get(f"/api/v1/products/{product_id}/serials", headers=s1)).json()
        by_number = {row["serial_number"]: row for row in listed}
        assert by_number[serials[0]]["store_id"] == s2["X-Store-ID"]
        assert by_number[serials[1]]["store_id"] == s2["X-Store-ID"]
        assert by_number[serials[2]]["store_id"] == s1["X-Store-ID"]

        assert await _on_hand(client, s1, product_id, space_gray) == 1
        assert await _on_hand(client, s2, product_id, space_gray) == 2


@pytest.mark.asyncio
async def test_serial_product_requires_serials_and_rejects_foreign_serials() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        s1, s2 = await _two_store_setup(client)
        product_id, space_gray = await _serial_variant_product(client, s1)
        serial = f"SN-{uuid.uuid4().hex[:8]}"
        await client.post(f"/api/v1/products/{product_id}/serials", headers=s1, json={"serials": [{"serial_number": serial, "variant_id": space_gray}]})

        missing = await client.post(
            "/api/v1/inventory/transfers",
            headers=s1,
            json={"to_store_id": s2["X-Store-ID"], "items": [{"product_id": product_id, "variant_id": space_gray, "quantity": 1}]},
        )
        assert missing.status_code == 400, missing.text

        unknown = await client.post(
            "/api/v1/inventory/transfers",
            headers=s1,
            json={"to_store_id": s2["X-Store-ID"], "items": [{"product_id": product_id, "variant_id": space_gray, "quantity": 1, "serial_numbers": ["DOES-NOT-EXIST"]}]},
        )
        assert unknown.status_code == 400, unknown.text

        moved = await client.post(
            "/api/v1/inventory/transfers",
            headers=s1,
            json={"to_store_id": s2["X-Store-ID"], "items": [{"product_id": product_id, "variant_id": space_gray, "quantity": 1, "serial_numbers": [serial]}]},
        )
        assert moved.status_code == 200, moved.text

        # The same serial now sits at the other store, so it can no longer leave branch one.
        again = await client.post(
            "/api/v1/inventory/transfers",
            headers=s1,
            json={"to_store_id": s2["X-Store-ID"], "items": [{"product_id": product_id, "variant_id": space_gray, "quantity": 1, "serial_numbers": [serial]}]},
        )
        assert again.status_code == 400, again.text


@pytest.mark.asyncio
async def test_non_serial_product_rejects_serial_numbers() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        s1, s2 = await _two_store_setup(client)
        product = await client.post(
            "/api/v1/products",
            headers=s1,
            json={"name": "Plain Laptop", "sku": f"PL-{uuid.uuid4().hex[:8]}", "price": "500.00", "opening_stock": 4},
        )
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]

        response = await client.post(
            "/api/v1/inventory/transfers",
            headers=s1,
            json={"to_store_id": s2["X-Store-ID"], "items": [{"product_id": product_id, "quantity": 1, "serial_numbers": ["NOPE-1"]}]},
        )
        assert response.status_code == 400, response.text


async def _serial_variant_pair(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str, str]:
    """A serial-tracked product with two colour variants; returns (product_id, space_gray, rose_gold)."""
    product = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Serial Laptop", "sku": f"SL-{uuid.uuid4().hex[:8]}", "price": "900.00", "track_serials": True},
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    variants = await client.put(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"variants": [
            {"sku": f"SGA-{uuid.uuid4().hex[:6]}", "name": "Space Gray"},
            {"sku": f"SGB-{uuid.uuid4().hex[:6]}", "name": "Rose Gold"},
        ]},
    )
    assert variants.status_code == 200, variants.text
    by_name = {row["name"]: row["id"] for row in variants.json()["variants"]}
    return product_id, by_name["Space Gray"], by_name["Rose Gold"]


async def _serial_variant_id(client: AsyncClient, headers: dict[str, str], product_id: str, serial_number: str) -> str | None:
    rows = (await client.get(f"/api/v1/products/{product_id}/serials", headers=headers)).json()
    return next(row["variant_id"] for row in rows if row["serial_number"] == serial_number)


@pytest.mark.asyncio
async def test_reassigning_a_serial_variant_moves_stock_and_unblocks_the_sale() -> None:
    """A unit filed under the wrong colour can be re-filed, and then sold on that variant."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        s1, _ = await _two_store_setup(client)
        product_id, space_gray, rose_gold = await _serial_variant_pair(client, s1)
        serial = f"SN-{uuid.uuid4().hex[:8]}"
        added = await client.post(
            f"/api/v1/products/{product_id}/serials",
            headers=s1,
            json={"serials": [{"serial_number": serial, "variant_id": space_gray}]},
        )
        assert added.status_code == 201, added.text
        assert await _on_hand(client, s1, product_id, space_gray) == 1
        assert await _on_hand(client, s1, product_id, rose_gold) == 0

        reassigned = await client.patch(f"/api/v1/serials/{added.json()[0]['id']}", headers=s1, json={"variant_id": rose_gold})
        assert reassigned.status_code == 200, reassigned.text
        assert reassigned.json()["variant_id"] == rose_gold
        assert await _on_hand(client, s1, product_id, space_gray) == 0
        assert await _on_hand(client, s1, product_id, rose_gold) == 1
        assert await _serial_variant_id(client, s1, product_id, serial) == rose_gold

        sale = await client.post(
            "/api/v1/orders",
            headers=s1,
            json={"items": [{"product_id": product_id, "variant_id": rose_gold, "quantity": 1, "serial_numbers": [serial]}], "payment_method": "cash"},
        )
        assert sale.status_code == 201, sale.text


@pytest.mark.asyncio
async def test_reactivating_a_sold_serial_into_a_new_variant_counts_stock_once() -> None:
    """Changing status and variant together must not double-count the unit."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        s1, _ = await _two_store_setup(client)
        product_id, space_gray, rose_gold = await _serial_variant_pair(client, s1)
        serial = f"SN-{uuid.uuid4().hex[:8]}"
        added = await client.post(
            f"/api/v1/products/{product_id}/serials",
            headers=s1,
            json={"serials": [{"serial_number": serial, "variant_id": space_gray}]},
        )
        assert added.status_code == 201, added.text
        serial_id = added.json()[0]["id"]

        sold = await client.patch(f"/api/v1/serials/{serial_id}", headers=s1, json={"status": "sold"})
        assert sold.status_code == 200, sold.text
        assert await _on_hand(client, s1, product_id, space_gray) == 0

        revived = await client.patch(f"/api/v1/serials/{serial_id}", headers=s1, json={"status": "in_stock", "variant_id": rose_gold})
        assert revived.status_code == 200, revived.text
        assert await _on_hand(client, s1, product_id, space_gray) == 0
        assert await _on_hand(client, s1, product_id, rose_gold) == 1


@pytest.mark.asyncio
async def test_delete_in_stock_serial_releases_its_stock() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        s1, _ = await _two_store_setup(client)
        product_id, space_gray, _ = await _serial_variant_pair(client, s1)
        serial = f"SN-{uuid.uuid4().hex[:8]}"
        added = await client.post(
            f"/api/v1/products/{product_id}/serials",
            headers=s1,
            json={"serials": [{"serial_number": serial, "variant_id": space_gray}]},
        )
        assert added.status_code == 201, added.text
        serial_id = added.json()[0]["id"]
        assert await _on_hand(client, s1, product_id, space_gray) == 1

        removed = await client.delete(f"/api/v1/serials/{serial_id}", headers=s1)
        assert removed.status_code == 200, removed.text
        assert removed.json()["serial_number"] == serial
        assert await _on_hand(client, s1, product_id, space_gray) == 0
        listed = (await client.get(f"/api/v1/products/{product_id}/serials", headers=s1)).json()
        assert all(row["serial_number"] != serial for row in listed)


@pytest.mark.asyncio
async def test_delete_sold_serial_is_rejected() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        s1, _ = await _two_store_setup(client)
        product_id, space_gray, _ = await _serial_variant_pair(client, s1)
        serial = f"SN-{uuid.uuid4().hex[:8]}"
        added = await client.post(
            f"/api/v1/products/{product_id}/serials",
            headers=s1,
            json={"serials": [{"serial_number": serial, "variant_id": space_gray}]},
        )
        assert added.status_code == 201, added.text
        serial_id = added.json()[0]["id"]
        sale = await client.post(
            "/api/v1/orders",
            headers=s1,
            json={"items": [{"product_id": product_id, "variant_id": space_gray, "quantity": 1, "serial_numbers": [serial]}], "payment_method": "cash"},
        )
        assert sale.status_code == 201, sale.text

        blocked = await client.delete(f"/api/v1/serials/{serial_id}", headers=s1)
        assert blocked.status_code == 400, blocked.text
