"""Cohort activation funnel: one denominator, monotonic stages.

Also covers the stage drilldown: why a stage leaks (validation/network/click/
dwell friction and abandon-survey answers) and which sessions stopped there,
including the ordered timeline.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import AnalyticsEvent
from tests.test_admin_funnel import cleanup, create_free_workspace, login_headers, promote_to_admin
from tests.test_telemetry import _batch, _event

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

async def _purge_analytics(email: str, company_id: str | None) -> None:
    """Remove telemetry rows before the tenant rows they point at disappear."""
    async with SessionLocal() as db:
        if company_id:
            await db.execute(
                text("DELETE FROM analytics_events WHERE company_id = :company_id"),
                {"company_id": company_id},
            )
            await db.execute(
                text("DELETE FROM analytics_sessions WHERE company_id = :company_id"),
                {"company_id": company_id},
            )
        await db.execute(
            text("DELETE FROM analytics_events WHERE user_id IN (SELECT id FROM users WHERE email = :email)"),
            {"email": email},
        )
        await db.execute(
            text("DELETE FROM analytics_sessions WHERE user_id IN (SELECT id FROM users WHERE email = :email)"),
            {"email": email},
        )
        await db.commit()


async def _new_workspace(client: AsyncClient, prefix: str) -> tuple[str, dict, dict]:
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    workspace, headers = await create_free_workspace(client, email)
    return email, workspace, headers


async def _seed_session(client: AsyncClient, headers: dict, events: list[dict]) -> str:
    session_id = str(uuid.uuid4())
    response = await client.post(
        "/api/v1/telemetry/events",
        headers=headers,
        json=_batch(session_id, events),
    )
    assert response.status_code == 202, response.text
    assert response.json()["accepted"] == len(events), response.text
    return session_id


async def test_journey_diagnostics_require_platform_admin() -> None:
    email = f"journey-diagnostics-denied-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            for url in (
                "/api/v1/admin/journeys/why?stage=account_created",
                "/api/v1/admin/journeys/sessions?stage=account_created",
                f"/api/v1/admin/journeys/sessions/{uuid.uuid4()}",
            ):
                denied = await client.get(url, headers=headers)
                assert denied.status_code == 403, (url, denied.text)
    finally:
        await _purge_analytics(email, company_id)
        await cleanup(email, company_id)


async def test_journey_why_explains_stage_friction() -> None:
    merchant_email = ""
    merchant_company_id = None
    operator_email = ""
    operator_company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            merchant_email, merchant_workspace, merchant_headers = await _new_workspace(client, "journey-why")
            merchant_company_id = merchant_workspace["company"]["id"]
            await _seed_session(
                client,
                merchant_headers,
                [
                    _event("ui.form_validation_failed", {"form": "signup", "field": "email", "rule": "required"}, route_key="signup"),
                    _event("ui.form_validation_failed", {"form": "signup", "field": "password", "rule": "min_length"}, route_key="signup"),
                    _event("error.network", {"endpoint_key": "auth.register", "status": 500, "error_code": "server"}, route_key="signup"),
                    _event("ui.dead_click", {"route_key": "signup"}, route_key="signup", element_key="signup.submit"),
                    _event("ui.rage_click", {"route_key": "signup", "clicks": 4}, route_key="signup", element_key="signup.submit"),
                    _event("page.left", {"dwell_ms": 4000, "scroll_pct": 40}, route_key="signup"),
                    _event("page.left", {"dwell_ms": 8000, "scroll_pct": 90}, route_key="signup"),
                ],
            )

            operator_email, operator_workspace, _ = await _new_workspace(client, "journey-why-operator")
            operator_company_id = operator_workspace["company"]["id"]
            await promote_to_admin(operator_email)
            admin_headers = await login_headers(client, operator_email)

            response = await client.get(
                "/api/v1/admin/journeys/why",
                headers=admin_headers,
                params={"stage": "account_created", "days": 30},
            )
            unknown = await client.get(
                "/api/v1/admin/journeys/why",
                headers=admin_headers,
                params={"stage": "not_a_stage"},
            )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["stage"] == "account_created"
        assert data["window_days"] == 30
        assert data["route_keys"] == ["signup", "login"]
        assert set(data) >= {
            "validation_failures",
            "network_failures",
            "dead_clicks",
            "rage_clicks",
            "dwell",
            "sample_events",
            "sample_sessions",
        }

        validation = {(row["form"], row["field"], row["rule"]): row["count"] for row in data["validation_failures"]}
        assert validation[("signup", "email", "required")] >= 1
        assert validation[("signup", "password", "min_length")] >= 1

        network = {(row["route_key"], row["endpoint_key"], row["status"]) for row in data["network_failures"]}
        assert ("signup", "auth.register", "500") in network

        assert any(row["element_key"] == "signup.submit" and row["count"] >= 1 for row in data["dead_clicks"])
        assert any(row["element_key"] == "signup.submit" and row["count"] >= 1 for row in data["rage_clicks"])

        # Two page.left events: 4s and 8s. Median is exact; p90 interpolates.
        assert data["dwell"]["samples"] >= 2
        assert data["dwell"]["median_ms"] == 6000.0
        assert data["dwell"]["p90_ms"] > data["dwell"]["median_ms"]
        assert data["sample_events"] >= 7
        assert data["sample_sessions"] >= 1

        assert unknown.status_code == 400
        detail = unknown.json()["detail"]
        assert "Unknown stage" in detail
        assert "account_created" in detail
    finally:
        if merchant_email:
            await _purge_analytics(merchant_email, merchant_company_id)
            await cleanup(merchant_email, merchant_company_id)
        if operator_email:
            await _purge_analytics(operator_email, operator_company_id)
            await cleanup(operator_email, operator_company_id)


async def test_journey_why_groups_abandon_survey_answers() -> None:
    merchant_email = ""
    merchant_company_id = None
    operator_email = ""
    operator_company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            merchant_email, merchant_workspace, merchant_headers = await _new_workspace(
                client, "journey-survey"
            )
            merchant_company_id = merchant_workspace["company"]["id"]
            await _seed_session(
                client,
                merchant_headers,
                [
                    # The setup plan step is where "too expensive" is expected.
                    _event(
                        "onboarding.abandon_survey",
                        {"step_key": "Choose your plan", "answer": "expensive"},
                        route_key="setup.plan",
                    ),
                    _event(
                        "onboarding.abandon_survey",
                        {"step_key": "Choose your plan", "answer": "expensive"},
                        route_key="setup.plan",
                    ),
                    _event(
                        "onboarding.abandon_survey",
                        {"step_key": "A few quick questions", "answer": "unclear"},
                        route_key="setup.questions",
                    ),
                    # "Other" arrives as the text the merchant chose to send.
                    _event(
                        "onboarding.abandon_survey",
                        {"step_key": "A few quick questions", "answer": "Which numbers do you want?"},
                        route_key="setup.questions",
                    ),
                    # An empty answer is not an answer and must not become a bucket.
                    _event(
                        "onboarding.abandon_survey",
                        {"step_key": "Company details", "answer": "   "},
                        route_key="setup.company",
                    ),
                    # Same event name, outside the stage's routes: out of scope.
                    _event(
                        "onboarding.abandon_survey",
                        {"step_key": "Choose your plan", "answer": "not this stage"},
                        route_key="pos",
                    ),
                ],
            )

            operator_email, operator_workspace, _ = await _new_workspace(
                client, "journey-survey-operator"
            )
            operator_company_id = operator_workspace["company"]["id"]
            await promote_to_admin(operator_email)
            admin_headers = await login_headers(client, operator_email)

            setup = await client.get(
                "/api/v1/admin/journeys/why",
                headers=admin_headers,
                params={"stage": "setup_opened", "days": 30},
            )
            # The same event name on a route this stage does not own is excluded.
            products = await client.get(
                "/api/v1/admin/journeys/why",
                headers=admin_headers,
                params={"stage": "first_product", "days": 30},
            )

        assert setup.status_code == 200, setup.text
        data = setup.json()
        assert data["survey_total"] >= 4
        counts = {row["answer"]: row["count"] for row in data["survey"]}
        assert counts["expensive"] >= 2
        assert counts["unclear"] >= 1
        assert counts["Which numbers do you want?"] >= 1
        assert "" not in counts
        assert "not this stage" not in counts
        # Ranked by count, and never more rows than the cap.
        assert len(data["survey"]) <= 10
        ordered = [row["count"] for row in data["survey"]]
        assert ordered == sorted(ordered, reverse=True)

        assert products.status_code == 200, products.text
        product_data = products.json()
        assert product_data["survey"] == []
        assert product_data["survey_total"] == 0
    finally:
        for email, company_id in (
            (merchant_email, merchant_company_id),
            (operator_email, operator_company_id),
        ):
            if email:
                await _purge_analytics(email, company_id)
                await cleanup(email, company_id)


async def test_journey_sessions_list_stalled_and_hide_internal() -> None:
    merchant_email = ""
    merchant_company_id = None
    operator_email = ""
    operator_company_id = None
    staff_email = ""
    staff_session_id = ""
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            merchant_email, merchant_workspace, merchant_headers = await _new_workspace(client, "journey-stop")
            merchant_company_id = merchant_workspace["company"]["id"]
            merchant_session_id = await _seed_session(
                client,
                merchant_headers,
                [
                    _event("page.viewed", {"title_key": "signup.title"}, route_key="signup"),
                    _event("page.left", {"dwell_ms": 30000}, route_key="signup"),
                ],
            )

            # A staff account is flagged internal at ingest, so it must never
            # appear in a stage's stalled list or open as a timeline.
            staff_email, _, staff_headers = await _new_workspace(client, "journey-stop-staff")
            await promote_to_admin(staff_email)
            staff_headers = await login_headers(client, staff_email)
            staff_session_id = await _seed_session(
                client,
                staff_headers,
                [_event("page.viewed", {"title_key": "signup.title"}, route_key="signup")],
            )

            operator_email, operator_workspace, _ = await _new_workspace(client, "journey-stop-operator")
            operator_company_id = operator_workspace["company"]["id"]
            await promote_to_admin(operator_email)
            admin_headers = await login_headers(client, operator_email)

            response = await client.get(
                "/api/v1/admin/journeys/sessions",
                headers=admin_headers,
                params={"stage": "account_created", "days": 30, "limit": 50},
            )
            limited = await client.get(
                "/api/v1/admin/journeys/sessions",
                headers=admin_headers,
                params={"stage": "account_created", "days": 30, "limit": 1},
            )
            staff_timeline = await client.get(
                f"/api/v1/admin/journeys/sessions/{staff_session_id}",
                headers=admin_headers,
            )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["stage"] == "account_created"
        assert data["window_days"] == 30
        assert data["route_keys"] == ["signup", "login"]
        assert data["limit"] == 50

        rows = {row["id"]: row for row in data["sessions"]}
        assert merchant_session_id in rows
        assert staff_session_id not in rows

        row = rows[merchant_session_id]
        assert set(row) == {
            "id",
            "user_id",
            "company_id",
            "started_at",
            "last_seen_at",
            "exit_route",
            "device_type",
            "browser",
            "locale",
            "source",
            "events",
        }
        assert row["company_id"] == merchant_company_id
        assert row["source"] == "web"
        assert row["device_type"] == "desktop"
        assert row["browser"] == "Chrome"
        assert row["locale"] == "en"
        assert row["events"] >= 2
        # The listing never leaks a fingerprint.
        assert "anonymous_id" not in row

        assert limited.status_code == 200
        assert limited.json()["limit"] == 1
        assert len(limited.json()["sessions"]) <= 1

        assert staff_timeline.status_code == 404
    finally:
        for email, company_id in (
            (merchant_email, merchant_company_id),
            (operator_email, operator_company_id),
            (staff_email, None),
        ):
            if email:
                await _purge_analytics(email, company_id)
                await cleanup(email, company_id)


async def test_journey_session_timeline_is_ordered_and_unknown_is_404() -> None:
    merchant_email = ""
    merchant_company_id = None
    operator_email = ""
    operator_company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            merchant_email, merchant_workspace, merchant_headers = await _new_workspace(client, "journey-timeline")
            merchant_company_id = merchant_workspace["company"]["id"]
            base = datetime.now(timezone.utc) - timedelta(minutes=10)
            session_id = await _seed_session(
                client,
                merchant_headers,
                [
                    _event(
                        "page.viewed",
                        {"title_key": "signup.title"},
                        occurred_at=base.isoformat(),
                        route_key="signup",
                    ),
                    _event(
                        "ui.form_validation_failed",
                        {"form": "signup", "field": "email", "rule": "required"},
                        occurred_at=(base + timedelta(minutes=2)).isoformat(),
                        route_key="signup",
                    ),
                    _event(
                        "page.left",
                        {"dwell_ms": 12000, "scroll_pct": 55},
                        occurred_at=(base + timedelta(minutes=4)).isoformat(),
                        route_key="signup",
                        element_key="signup.form",
                    ),
                ],
            )

            operator_email, operator_workspace, _ = await _new_workspace(client, "journey-timeline-operator")
            operator_company_id = operator_workspace["company"]["id"]
            await promote_to_admin(operator_email)
            admin_headers = await login_headers(client, operator_email)

            response = await client.get(
                f"/api/v1/admin/journeys/sessions/{session_id}",
                headers=admin_headers,
            )
            missing = await client.get(
                f"/api/v1/admin/journeys/sessions/{uuid.uuid4()}",
                headers=admin_headers,
            )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["id"] == session_id
        assert data["company_id"] == merchant_company_id
        assert data["truncated"] is False
        assert [event["name"] for event in data["events"]] == [
            "page.viewed",
            "ui.form_validation_failed",
            "page.left",
        ]
        timestamps = [event["occurred_at"] for event in data["events"]]
        assert timestamps == sorted(timestamps)

        last = data["events"][-1]
        assert last["route_key"] == "signup"
        assert last["element_key"] == "signup.form"
        assert last["properties"]["dwell_ms"] == 12000
        assert "anonymous_id" not in data
        for event in data["events"]:
            assert set(event) == {"occurred_at", "name", "route_key", "element_key", "duration_ms", "properties"}

        assert missing.status_code == 404
    finally:
        for email, company_id in (
            (merchant_email, merchant_company_id),
            (operator_email, operator_company_id),
        ):
            if email:
                await _purge_analytics(email, company_id)
                await cleanup(email, company_id)
