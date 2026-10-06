"""The GDT invoice CSV export must be UTF-8 BOM-prefixed for Excel."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_gdt_csv_is_bom_prefixed() -> None:
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "GDT Store", "Main", plan="pro", email_prefix="gdt")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            product = (await client.post("/api/v1/products", headers=store_headers, json={"name": "GDT Item", "sku": f"GDT-{uuid.uuid4().hex[:8]}", "price": "10.00", "opening_stock": 5})).json()
            order = await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product["id"], "quantity": 1}], "payment_method": "cash"})
            assert order.status_code == 201, order.text

            export = await client.get("/api/v1/reports/gdt-csv", headers=store_headers)
            assert export.status_code == 200, export.text
            assert export.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
            text = export.content.decode("utf-8-sig")
            assert "document_number" in text
            assert order.json()["order_number"] in text
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
