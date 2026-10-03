from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _sold_serial_id(client, headers, store_headers) -> str:
    category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
    product = await client.post(
        "/api/v1/products",
        headers=store_headers,
        json={"name": "Tablet Z", "sku": f"WR-{uuid.uuid4().hex[:8]}", "price": "500.00", "category_id": category_id, "opening_stock": 0, "track_serials": True},
    )
    product_id = product.json()["id"]
    serial_number = f"SN-{uuid.uuid4().hex[:10]}"
    await client.post(f"/api/v1/products/{product_id}/serials", headers=store_headers, json={"serials": [{"serial_number": serial_number}]})
    await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1, "serial_numbers": [serial_number]}], "payment_method": "cash"})
    serials = (await client.get(f"/api/v1/products/{product_id}/serials", headers=store_headers)).json()
    return serials[0]["id"]


@pytest.mark.asyncio
async def test_warranty_claim_cost_appears_in_the_summary_report() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Warranty Reports", "Main", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            serial_id = await _sold_serial_id(client, headers, store_headers)

            claim = (await client.post("/api/v1/warranty-claims", headers=store_headers, json={"serial_id": serial_id, "issue": "No charge"})).json()
            await client.post(f"/api/v1/warranty-claims/{claim['id']}/decide", headers=store_headers, json={"approve": True, "resolution": "repair"})
            await client.post(f"/api/v1/warranty-claims/{claim['id']}/resolve", headers=store_headers, json={"resolution": "repair", "cost": "40.00"})

            summary = (await client.get("/api/v1/reports/summary", headers=store_headers)).json()
            assert summary["warranty_claim_count"] == 1
            assert summary["warranty_claim_cost"] == "40.00"
    finally:
        await cleanup_company(company_id, [email] if email else [])
