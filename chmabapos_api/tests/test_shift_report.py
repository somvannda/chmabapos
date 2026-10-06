"""Owner Z-report email on shift close."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_shift_close_emails_owner_the_summary() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Shift Report Store", "Main", plan="starter", email_prefix="shift-report")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product_id = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={"name": "Shift Latte", "sku": f"SR-{uuid.uuid4().hex[:8]}", "price": "4.50", "category_id": category_id, "opening_stock": 10},
                )
            ).json()["id"]
            opened = await client.post("/api/v1/shifts/open", headers=store_headers, json={"opening_float": 0})
            assert opened.status_code == 201, opened.text
            order = await client.post(
                "/api/v1/orders",
                headers=store_headers,
                json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"},
            )
            assert order.status_code == 201, order.text

            await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"preferences": {"notifications": {"shift_report": True}}})
            closed = await client.post(f"/api/v1/shifts/{opened.json()['id']}/close", headers=store_headers, json={"counted_cash": "4.50"})
            assert closed.status_code == 200, closed.text

            async with SessionLocal() as db:
                rows = (
                    await db.execute(
                        select(EmailSend).where(EmailSend.recipient_email == email, EmailSend.source == "store_note")
                    )
                ).scalars().all()
            reports = [row for row in rows if row.subject.startswith("Shift closed")]
            assert len(reports) == 1
            assert "<!DOCTYPE html>" in reports[0].body_html
            assert "Expected cash" in reports[0].body_html
    finally:
        if email:
            async with SessionLocal() as db:
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
                await db.commit()
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_shift_expected_cash_reconciles_a_full_cash_refund() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Shift Refund Store", "Main", plan="starter", email_prefix="shift-refund")
            email, company_id = ctx["email"], ctx["company_id"]
            headers, store_headers = ctx["headers"], ctx["store_headers"]
            category_id = (await client.get("/api/v1/categories", headers=headers)).json()[0]["id"]
            product_id = (
                await client.post(
                    "/api/v1/products",
                    headers=store_headers,
                    json={"name": "Shift Refund Item", "sku": f"SR-{uuid.uuid4().hex[:8]}", "price": "4.50", "category_id": category_id, "opening_stock": 10},
                )
            ).json()["id"]
            opened = await client.post("/api/v1/shifts/open", headers=store_headers, json={"opening_float": 0})
            assert opened.status_code == 201, opened.text

            order = (await client.post("/api/v1/orders", headers=store_headers, json={"items": [{"product_id": product_id, "quantity": 1}], "payment_method": "cash"})).json()
            refund = await client.post(f"/api/v1/orders/{order['id']}/refund", headers=store_headers, json={"method": "cash", "items": [{"product_id": product_id, "quantity": 1}]})
            assert refund.status_code == 201, refund.text

            closed = await client.post(f"/api/v1/shifts/{opened.json()['id']}/close", headers=store_headers, json={"counted_cash": "0.00"})
            assert closed.status_code == 200, closed.text
            body = closed.json()
            # Cash in equals cash out: the drawer is back to the opening float.
            assert float(body["expected_cash"]) == 0.0
            assert float(body["difference"]) == 0.0
            # The (later refunded) sale still counts as gross sales.
            assert float(body["sales_total"]) == float(order["total"])
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
