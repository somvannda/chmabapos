from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _create_product(client, store_headers, category_id: str, name: str, price: str, stock: int = 20) -> dict:
    response = await client.post(
        "/api/v1/products",
        headers=store_headers,
        json={"name": name, "sku": f"SC-{uuid.uuid4().hex[:8]}", "price": price, "category_id": category_id, "opening_stock": stock},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_seat_lines_are_distinct_and_settle_snapshots_seat_and_course() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Seat Store", "Main Floor", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            cola = await _create_product(client, store_headers, category_id, "Cola", "2.00")

            # The same drink for two seats is two lines — seat is part of identity.
            held = await client.post(
                "/api/v1/held-orders",
                headers=store_headers,
                json={"items": [
                    {"product_id": cola["id"], "quantity": 1, "seat": 1, "course": "drinks"},
                    {"product_id": cola["id"], "quantity": 1, "seat": 2, "course": "drinks"},
                ]},
            )
            assert held.status_code == 201, held.text
            assert [item["seat"] for item in held.json()["items"]] == [1, 2]
            assert all(item["course"] == "drinks" for item in held.json()["items"])

            # Settling snapshots seat/course onto the order line.
            sale = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": cola["id"], "quantity": 1, "seat": 2, "course": "mains"}], "payment_method": "cash"},
            )
            assert sale.status_code == 201, sale.text
            line = sale.json()["items"][0]
            assert line["seat"] == 2
            assert line["course"] == "mains"
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_fire_by_course_marks_only_that_course() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Fire Store", "Main Floor", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            starter = await _create_product(client, store_headers, category_id, "Soup", "3.00")
            main = await _create_product(client, store_headers, category_id, "Steak", "9.00")

            held = await client.post(
                "/api/v1/held-orders",
                headers=store_headers,
                json={"items": [
                    {"product_id": starter["id"], "quantity": 1, "course": "starters"},
                    {"product_id": main["id"], "quantity": 1, "course": "mains"},
                ]},
            )
            assert held.status_code == 201, held.text
            held_id = held.json()["id"]

            fired = await client.post(f"/api/v1/held-orders/{held_id}/fire", headers=store_headers, json={"course": "starters"})
            assert fired.status_code == 200, fired.text
            by_course = {item["course"]: item for item in fired.json()["items"]}
            assert by_course["starters"]["fired_at"] is not None
            assert by_course["mains"]["fired_at"] is None

            # Nothing left in that course to fire.
            again = await client.post(f"/api/v1/held-orders/{held_id}/fire", headers=store_headers, json={"course": "starters"})
            assert again.status_code == 400

            # Firing with no course fires everything still unfired.
            all_fired = await client.post(f"/api/v1/held-orders/{held_id}/fire", headers=store_headers, json={})
            assert all_fired.status_code == 200, all_fired.text
            assert all(item["fired_at"] is not None for item in all_fired.json()["items"])
    finally:
        await cleanup_company(company_id, [email] if email else [])
