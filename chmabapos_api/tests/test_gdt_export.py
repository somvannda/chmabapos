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


@pytest.mark.asyncio
async def test_a_khr_export_states_riel_in_whole_riel() -> None:
    """A tax file must not claim a subunit the currency does not have.

    Each row already carries its own currency, so a mixed company cannot be summed
    by accident; the remaining risk was the figure itself - "3333.00 KHR" reads as a
    riel with a hundredth, which does not exist.
    """
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "GDT Riel Store", "Main", plan="pro", email_prefix="gdt-khr")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            enabled = await client.put("/api/v1/settings/currencies", headers=headers, json={"primary_code": "USD", "enabled_codes": ["USD", "KHR"]})
            assert enabled.status_code == 200, enabled.text
            configured = await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"currency_code": "KHR"})
            assert configured.status_code == 200, configured.text
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={"name": "Riel Item", "sku": f"GDTK-{uuid.uuid4().hex[:8]}", "price": "3333", "opening_stock": 5},
                )
            ).json()
            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product["id"], "quantity": 1}], "payment_method": "cash"},
            )
            assert order.status_code == 201, order.text

            export = await client.get("/api/v1/reports/gdt-csv", headers=store_headers)
            assert export.status_code == 200, export.text
            text = export.content.decode("utf-8-sig")
            row = next(line for line in text.splitlines() if order.json()["order_number"] in line)
            assert ",333,3666,KHR," in row, row
            assert "3666.00" not in row, row
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
