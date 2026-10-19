from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_dining_areas_tables_and_area_delete_detaches_tables() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Dining Store", "Main Floor", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]
            store_headers = ctx["store_headers"]

            assert (await client.get("/api/v1/dining/areas", headers=store_headers)).json() == []

            terrace = await client.post("/api/v1/dining/areas", headers=store_headers, json={"name": "Terrace", "position": 1})
            assert terrace.status_code == 201, terrace.text
            area_id = terrace.json()["id"]
            # Names are unique per store.
            assert (await client.post("/api/v1/dining/areas", headers=store_headers, json={"name": "Terrace"})).status_code == 409

            table = await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "T1", "area_id": area_id, "seats": 4})
            assert table.status_code == 201, table.text
            table_id = table.json()["id"]
            assert table.json()["status"] == "available" and table.json()["seats"] == 4

            # Duplicate name and unknown area are rejected.
            assert (await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "T1"})).status_code == 409
            assert (await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "T2", "area_id": "00000000-0000-0000-0000-000000000000"})).status_code == 400
            # Unknown status is rejected at the boundary.
            assert (await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "T3", "status": "napping"})).status_code == 422

            # Status updates round-trip.
            occupied = await client.patch(f"/api/v1/dining/tables/{table_id}", headers=store_headers, json={"status": "occupied"})
            assert occupied.status_code == 200 and occupied.json()["status"] == "occupied"

            # Deleting the area detaches (does not delete) its tables.
            assert (await client.delete(f"/api/v1/dining/areas/{area_id}", headers=store_headers)).status_code == 200
            tables = (await client.get("/api/v1/dining/tables", headers=store_headers)).json()
            assert len(tables) == 1 and tables[0]["area_id"] is None

            assert (await client.delete(f"/api/v1/dining/tables/{table_id}", headers=store_headers)).status_code == 200
            assert (await client.get("/api/v1/dining/tables", headers=store_headers)).json() == []

            # Unknown ids are 404.
            assert (await client.patch("/api/v1/dining/tables/00000000-0000-0000-0000-000000000000", headers=store_headers, json={"status": "cleaning"})).status_code == 404
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_rotating_a_table_qr_retires_the_old_code() -> None:
    """A leaked table code can be killed without deleting the table, and only the
    new code resolves afterwards."""
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Rotate Store", "Main Floor", plan="pro", email_prefix="rotate")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product = (await client.post("/api/v1/products", headers=store_headers, json={"name": "Tea", "sku": f"ROT-{uuid.uuid4().hex[:8]}", "price": "2.00", "category_id": category_id, "opening_stock": 5})).json()
            table = (await client.post("/api/v1/dining/tables", headers=store_headers, json={"name": "T1", "seats": 2})).json()
            await client.patch(f"/api/v1/stores/{ctx['store_id']}/public-order", headers=headers, json={"enabled": True})

            old_code = table["qr_token"]
            assert (await client.get(f"/api/v1/public/order/{old_code}")).json()["table_name"] == "T1"

            rotated = await client.post(f"/api/v1/dining/tables/{table['id']}/rotate-qr", headers=store_headers, json={})
            assert rotated.status_code == 200, rotated.text
            new_code = rotated.json()["qr_token"]
            assert new_code and new_code != old_code
            # The table itself is untouched.
            assert rotated.json()["id"] == table["id"] and rotated.json()["name"] == "T1"

            # The retired code no longer resolves, on either surface.
            assert (await client.get(f"/api/v1/public/order/{old_code}")).status_code == 404
            retired_submit = await client.post(f"/api/v1/public/order/{old_code}", json={"items": [{"product_id": product["id"], "quantity": 1}]})
            assert retired_submit.status_code == 404

            # The new code resolves and still attributes the table.
            assert (await client.get(f"/api/v1/public/order/{new_code}")).json()["table_name"] == "T1"
            placed = await client.post(f"/api/v1/public/order/{new_code}", json={"items": [{"product_id": product["id"], "quantity": 1}]})
            assert placed.status_code == 201, placed.text
            assert placed.json()["table_id"] == table["id"]

            assert (await client.post("/api/v1/dining/tables/00000000-0000-0000-0000-000000000000/rotate-qr", headers=store_headers, json={})).status_code == 404
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_table_management_is_available_on_starter_but_not_free() -> None:
    # Starter and Pro include table management; Free is still blocked.
    for plan, expected in (("free", 403), ("starter", 200)):
        email: str | None = None
        company_id: str | None = None
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                ctx = await register_and_setup(client, f"Dining {plan}", "Main", plan=plan)
                email, company_id = ctx["email"], ctx["company_id"]
                response = await client.get("/api/v1/dining/areas", headers=ctx["store_headers"])
                assert response.status_code == expected, f"{plan} table management status"
        finally:
            await cleanup_company(company_id, [email] if email else [])
