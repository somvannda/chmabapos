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
        json={"name": name, "sku": f"SL-{uuid.uuid4().hex[:8]}", "price": price, "category_id": category_id, "opening_stock": stock},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_update_held_line_seat_and_course() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Seat Line Store", "Main Floor", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            cola = await _create_product(client, store_headers, category_id, "Cola", "2.00")

            held = await client.post(
                "/api/v1/held-orders",
                headers=store_headers,
                json={"items": [
                    {"product_id": cola["id"], "quantity": 1, "seat": 1},
                    {"product_id": cola["id"], "quantity": 1, "seat": 3},
                ]},
            )
            assert held.status_code == 201, held.text
            held_id = held.json()["id"]
            first_key, second_key = held.json()["items"][0]["line_key"], held.json()["items"][1]["line_key"]

            # Moving the seat-3 line onto seat 1 collides with the existing line.
            clash = await client.patch(f"/api/v1/held-orders/{held_id}/items", headers=store_headers, json={"line_key": second_key, "seat": 1})
            assert clash.status_code == 409

            # Re-seating and re-coursing a line works and re-keys it.
            moved = await client.patch(f"/api/v1/held-orders/{held_id}/items", headers=store_headers, json={"line_key": second_key, "seat": 4, "course": "mains"})
            assert moved.status_code == 200, moved.text
            by_seat = {item["seat"]: item for item in moved.json()["items"]}
            assert by_seat[4]["course"] == "mains"
            assert by_seat[4]["line_key"] != second_key

            # A course change alone does not fork the line.
            coursed = await client.patch(f"/api/v1/held-orders/{held_id}/items", headers=store_headers, json={"line_key": first_key, "seat": 1, "course": "starters"})
            assert coursed.status_code == 200, coursed.text
            assert {item["seat"]: item["course"] for item in coursed.json()["items"]}[1] == "starters"
    finally:
        await cleanup_company(company_id, [email] if email else [])
