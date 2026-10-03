from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _create_serial_product(client, headers, store_headers, name: str = "Phone X") -> dict:
    category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
    product = await client.post(
        "/api/v1/products",
        headers=store_headers,
        json={"name": name, "sku": f"WC-{uuid.uuid4().hex[:8]}", "price": "800.00", "category_id": category_id, "opening_stock": 0, "track_serials": True},
    )
    assert product.status_code == 201, product.text
    return product.json()


async def _sell_one_serial(client, store_headers, product: dict) -> str:
    serial_number = f"SN-{uuid.uuid4().hex[:10]}"
    added = await client.post(f"/api/v1/products/{product['id']}/serials", headers=store_headers, json={"serials": [{"serial_number": serial_number}]})
    assert added.status_code == 201, added.text
    sold = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product["id"], "quantity": 1, "serial_numbers": [serial_number]}], "payment_method": "cash"})
    assert sold.status_code == 201, sold.text
    return serial_number


async def _serial_id(client, store_headers, product_id: str) -> str:
    serials = (await client.get(f"/api/v1/products/{product_id}/serials", headers=store_headers)).json()
    return serials[0]["id"]


@pytest.mark.asyncio
async def test_warranty_claim_repair_lifecycle() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Warranty Store", "Main", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product = await _create_serial_product(client, headers, store_headers)
            await _sell_one_serial(client, store_headers, product)
            serial_id = await _serial_id(client, store_headers, product["id"])

            claim = await client.post("/api/v1/warranty-claims", headers=store_headers, json={"serial_id": serial_id, "issue": "Battery swelling"})
            assert claim.status_code == 201, claim.text
            body = claim.json()
            assert body["status"] == "open"
            assert body["claim_number"]
            assert len(body["events"]) == 1

            decided = await client.post(f"/api/v1/warranty-claims/{body['id']}/decide", headers=store_headers, json={"approve": True, "resolution": "repair"})
            assert decided.status_code == 200, decided.text
            assert decided.json()["status"] == "approved"

            resolved = await client.post(f"/api/v1/warranty-claims/{body['id']}/resolve", headers=store_headers, json={"resolution": "repair", "cost": "25.00", "note": "Battery replaced"})
            assert resolved.status_code == 200, resolved.text
            final = resolved.json()
            assert final["status"] == "closed"
            assert final["resolution"] == "repair"
            assert final["service_ticket_id"]
            assert [event["to_status"] for event in final["events"]] == ["open", "approved", "closed"]
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_warranty_claim_rejects_unsold_serial() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Warranty Guard", "Main", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product = await _create_serial_product(client, headers, store_headers)
            serial_number = f"SN-{uuid.uuid4().hex[:10]}"
            await client.post(f"/api/v1/products/{product['id']}/serials", headers=store_headers, json={"serials": [{"serial_number": serial_number}]})
            serial_id = await _serial_id(client, store_headers, product["id"])
            blocked = await client.post("/api/v1/warranty-claims", headers=store_headers, json={"serial_id": serial_id, "issue": "Dead pixels"})
            assert blocked.status_code == 400
    finally:
        await cleanup_company(company_id, [email] if email else [])
