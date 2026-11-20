"""Cohort activation funnel: one denominator, monotonic stages."""
from __future__ import annotations

import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import AnalyticsEvent
from tests.test_admin_funnel import cleanup, create_free_workspace, login_headers, promote_to_admin

STAGE_KEYS = [
    "account_created",
    "email_verified",
    "first_login",
    "setup_opened",
    "workspace_created",
    "first_product",
    "shift_opened",
    "first_sale",
    "second_sale",
]


async def test_journey_funnel_requires_platform_admin() -> None:
    email = f"journey-denied-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            denied = await client.get("/api/v1/admin/journeys/funnel", headers=headers)
        assert denied.status_code == 403
    finally:
        await cleanup(email, company_id)


async def test_journey_funnel_is_monotonic_and_uses_one_cohort() -> None:
    email = f"journey-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            store_id = workspace["store"]["id"]
            product = await client.post(
                "/api/v1/products",
                headers={**headers, "X-Store-ID": store_id},
                json={
                    "name": "Journey Widget",
                    "sku": f"JW-{uuid.uuid4().hex[:8]}",
                    "price": "5.00",
                    "opening_stock": 2,
                },
            )
            assert product.status_code == 201
            order = await client.post(
                "/api/v1/orders",
                headers={**headers, "X-Store-ID": store_id},
                json={
                    "items": [{"product_id": product.json()["id"], "quantity": 1}],
                    "payment_method": "cash",
                },
            )
            assert order.status_code == 201

        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)
            response = await client.get("/api/v1/admin/journeys/funnel", headers=admin_headers, params={"days": 30})

        assert response.status_code == 200
        data = response.json()
        assert data["cohort"] == "companies"
        assert data["total"] >= 1
        assert [stage["key"] for stage in data["stages"]] == STAGE_KEYS

        counts = [stage["count"] for stage in data["stages"]]
        assert counts == sorted(counts, reverse=True), counts

        first = data["stages"][0]
        assert first["from_previous"] is None
        assert first["from_start"] == 1
        assert first["count"] == data["total"]

        by_key = {stage["key"]: stage for stage in data["stages"]}
        assert by_key["workspace_created"]["count"] >= 1
        assert by_key["first_product"]["count"] >= 1
        assert by_key["first_sale"]["count"] >= 1
        # A browser-only stage explains the journey but is not a conversion.
        assert by_key["setup_opened"]["authoritative"] is False
        assert by_key["workspace_created"]["authoritative"] is True
        for stage in data["stages"]:
            assert stage["stalled"] == data["total"] - stage["count"]
            assert stage["median_seconds"] is None or stage["median_seconds"] >= 0
    finally:
        await cleanup(email, company_id)


async def test_paid_order_emits_an_authoritative_milestone() -> None:
    email = f"journey-sale-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            store_id = workspace["store"]["id"]
            product = await client.post(
                "/api/v1/products",
                headers={**headers, "X-Store-ID": store_id},
                json={
                    "name": "Paid Milestone Widget",
                    "sku": f"PM-{uuid.uuid4().hex[:8]}",
                    "price": "5.00",
                    "opening_stock": 1,
                },
            )
            assert product.status_code == 201
            order = await client.post(
                "/api/v1/orders",
                headers={**headers, "X-Store-ID": store_id},
                json={
                    "items": [{"product_id": product.json()["id"], "quantity": 1}],
                    "payment_method": "cash",
                },
            )
            assert order.status_code == 201
            assert order.json()["status"] == "paid"

        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(AnalyticsEvent).where(
                        AnalyticsEvent.company_id == uuid.UUID(company_id),
                        AnalyticsEvent.name == "order.paid",
                    )
                )
            ).scalars().all()

        assert len(rows) == 1
        event = rows[0]
        assert event.source == "api"
        assert event.context == {"authoritative": True}
        assert str(event.store_id) == store_id
        assert event.properties["payment_method"] == "cash"
        assert event.properties["currency"] == "USD"
        assert event.properties["items"] == 1
        assert event.properties["total_bucket"] == "0-10"
        # The milestone describes the sale, never the buyer.
        assert "Paid Milestone" not in str(event.properties)
    finally:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM analytics_events WHERE company_id = :company_id"), {"company_id": company_id})
            await db.commit()
        await cleanup(email, company_id)


async def test_journey_health_is_admin_only_and_reports_ingest() -> None:
    email = f"journey-health-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            denied = await client.get("/api/v1/admin/journeys/health", headers=headers)
        assert denied.status_code == 403

        await promote_to_admin(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = await login_headers(client, email)
            response = await client.get("/api/v1/admin/journeys/health", headers=admin_headers, params={"hours": 24})
        assert response.status_code == 200
        data = response.json()
        assert set(data) >= {"window_hours", "events", "sessions", "users", "last_event_at", "lag_seconds", "partitions"}
        assert data["window_hours"] == 24
        assert data["events"] >= 1
        assert data["partitions"] >= 1
        assert data["lag_seconds"] is None or data["lag_seconds"] >= 0
    finally:
        await cleanup(email, company_id)
