"""Product telemetry: collector, sanitizer, identity and rollups.

The collector is the one public write endpoint that exists purely so we can
understand drop-off, so these tests cover the failure modes that would make the
data quietly wrong: a secret stored, a duplicate counted twice, a client
choosing its own tenant, or a stale token turning into an error over a sale.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, text

from app.analytics import emit, normalize_route, rebuild_rollups
from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import AnalyticsEvent, AnalyticsSession, User


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(name: str = "page.viewed", props: dict | None = None, **overrides) -> dict:
    payload = {
        "id": str(uuid.uuid4()),
        "name": name,
        "occurred_at": _now(),
        "route": "/shop/products",
        "route_key": "products",
        "props": props or {},
    }
    payload.update(overrides)
    return payload


def _batch(session_id: str, events: list[dict], anonymous_id: str | None = None, source: str = "web") -> dict:
    return {
        "source": source,
        "app_version": "test-1.0",
        "session": {
            "id": session_id,
            "anonymous_id": anonymous_id or str(uuid.uuid4()),
            "started_at": _now(),
            "entry_route": "/",
            "platform": "web",
            "os": "Windows",
            "browser": "Chrome",
            "device_type": "desktop",
            "locale": "en",
            "timezone": "Asia/Phnom_Penh",
        },
        "events": events,
    }


async def _cleanup_session(session_id: str) -> None:
    async with SessionLocal() as db:
        await db.execute(delete(AnalyticsEvent).where(AnalyticsEvent.session_id == uuid.UUID(session_id)))
        await db.execute(delete(AnalyticsSession).where(AnalyticsSession.id == uuid.UUID(session_id)))
        await db.commit()


async def _create_workspace(email: str) -> tuple[dict, dict]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "full_name": "Telemetry Owner", "password": "strong-password"},
        )
        assert register.status_code == 201
        await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        setup = await client.post(
            "/api/v1/workspaces/setup",
            headers=headers,
            json={
                "company_name": "Telemetry Store",
                "store_name": "Main Counter",
                "country": "Cambodia",
                "currency_code": "USD",
                "plan_code": "free",
            },
        )
        assert setup.status_code == 201
        return setup.json(), headers


async def _cleanup_workspace(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        await db.execute(
            text("DELETE FROM analytics_events WHERE company_id = :company_id"), {"company_id": company_id}
        )
        await db.execute(
            text("DELETE FROM analytics_sessions WHERE company_id = :company_id"), {"company_id": company_id}
        )
        await db.execute(
            text("DELETE FROM platform_activities WHERE company_id = :company_id OR user_id IN (SELECT id FROM users WHERE email = :email)"),
            {"company_id": company_id, "email": email},
        )
        await db.execute(
            text("DELETE FROM analytics_events WHERE user_id IN (SELECT id FROM users WHERE email = :email)"),
            {"email": email},
        )
        await db.execute(
            text("DELETE FROM analytics_sessions WHERE user_id IN (SELECT id FROM users WHERE email = :email)"),
            {"email": email},
        )
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM stock_movements WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM inventory_balances WHERE store_id IN (SELECT id FROM stores WHERE company_id = :company_id)",
                "DELETE FROM product_variants WHERE product_id IN (SELECT id FROM products WHERE company_id = :company_id)",
                "DELETE FROM products WHERE company_id = :company_id",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM categories WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]
            for statement in statements:
                await db.execute(text(statement), parameters)
        await db.execute(
            text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"),
            {"email": email},
        )
        await db.execute(text("DELETE FROM auth_sessions WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


async def test_batch_is_stored_and_linked_to_its_session() -> None:
    session_id = str(uuid.uuid4())
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/telemetry/events",
                json=_batch(session_id, [_event("page.viewed"), _event("ui.click", {"element_key": "pos.checkout.pay"})]),
            )
        assert response.status_code == 202
        assert response.json() == {"accepted": 2, "dropped": 0}

        async with SessionLocal() as db:
            events = (
                await db.execute(
                    select(AnalyticsEvent).where(AnalyticsEvent.session_id == uuid.UUID(session_id))
                )
            ).scalars().all()
            assert {event.name for event in events} == {"page.viewed", "ui.click"}
            assert all(event.source == "web" for event in events)
            session = await db.get(AnalyticsSession, uuid.UUID(session_id))
            assert session is not None
            assert session.entry_route == "/"
    finally:
        await _cleanup_session(session_id)


async def test_unknown_event_is_dropped_not_stored() -> None:
    session_id = str(uuid.uuid4())
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/telemetry/events",
                json=_batch(session_id, [_event("ui.mystery_control")]),
            )
        assert response.status_code == 202
        assert response.json() == {"accepted": 0, "dropped": 1}
        async with SessionLocal() as db:
            stored = await db.scalar(
                select(AnalyticsEvent.id).where(AnalyticsEvent.session_id == uuid.UUID(session_id))
            )
        assert stored is None
    finally:
        await _cleanup_session(session_id)


async def test_secrets_and_personal_details_are_stripped() -> None:
    session_id = str(uuid.uuid4())
    try:
        props = {
            "password": "hunter2",
            "access_token": "secret-token",
            "phone": "+855 12 345 678",
            "email": "owner@example.com",
            "safe": "yes",
            "nested": {"card_number": "4111111111111111", "ok": 1},
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/telemetry/events",
                json=_batch(
                    session_id,
                    [_event("ui.form_validation_failed", props, route="/reset-password?token=SECRET#frag")],
                ),
            )
        assert response.status_code == 202
        async with SessionLocal() as db:
            event = (
                await db.execute(
                    select(AnalyticsEvent).where(AnalyticsEvent.session_id == uuid.UUID(session_id))
                )
            ).scalar_one()
        assert event.properties == {"safe": "yes", "nested": {"ok": 1}}
        assert event.route == "/reset-password"
        assert "SECRET" not in (event.route or "")
        assert "hunter2" not in str(event.properties)
        assert "4111" not in str(event.properties)
    finally:
        await _cleanup_session(session_id)


async def test_duplicate_event_id_is_counted_once() -> None:
    session_id = str(uuid.uuid4())
    duplicate = _event("page.viewed")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post("/api/v1/telemetry/events", json=_batch(session_id, [duplicate]))
            second = await client.post("/api/v1/telemetry/events", json=_batch(session_id, [duplicate]))
        assert first.json()["accepted"] == 1
        assert second.json()["accepted"] == 0
        assert second.json()["dropped"] == 1
        async with SessionLocal() as db:
            count = await db.scalar(
                select(func.count())
                .select_from(AnalyticsEvent)
                .where(AnalyticsEvent.session_id == uuid.UUID(session_id))
            )
        assert count == 1
    finally:
        await _cleanup_session(session_id)


async def test_invalid_bearer_token_stays_anonymous() -> None:
    session_id = str(uuid.uuid4())
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/telemetry/events",
                headers={"Authorization": "Bearer not-a-real-token"},
                json=_batch(session_id, [_event()]),
            )
        assert response.status_code == 202
        assert response.json()["accepted"] == 1
        async with SessionLocal() as db:
            session = await db.get(AnalyticsSession, uuid.UUID(session_id))
            assert session is not None and session.user_id is None
    finally:
        await _cleanup_session(session_id)


async def test_tenant_is_derived_from_the_token_not_the_body() -> None:
    email = f"telemetry-{uuid.uuid4().hex[:10]}@example.com"
    workspace, headers = await _create_workspace(email)
    company_id = workspace["company"]["id"]
    session_id = str(uuid.uuid4())
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/telemetry/events",
                headers=headers,
                json=_batch(session_id, [_event()]),
            )
        assert response.status_code == 202
        async with SessionLocal() as db:
            event = (
                await db.execute(
                    select(AnalyticsEvent).where(AnalyticsEvent.session_id == uuid.UUID(session_id))
                )
            ).scalar_one()
            session = await db.get(AnalyticsSession, uuid.UUID(session_id))
        assert str(event.company_id) == company_id
        assert str(event.store_id) == workspace["store"]["id"]
        assert session is not None and str(session.company_id) == company_id
    finally:
        await _cleanup_session(session_id)
        await _cleanup_workspace(email, company_id)


async def test_crawler_user_agent_is_ignored() -> None:
    session_id = str(uuid.uuid4())
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/telemetry/events",
                headers={"User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"},
                json=_batch(session_id, [_event()]),
            )
        assert response.status_code == 202
        assert response.json() == {"accepted": 0, "dropped": 0}
        async with SessionLocal() as db:
            session = await db.get(AnalyticsSession, uuid.UUID(session_id))
        assert session is None
    finally:
        await _cleanup_session(session_id)


async def test_collector_can_be_disabled(monkeypatch) -> None:
    session_id = str(uuid.uuid4())
    monkeypatch.setattr(settings, "analytics_enabled", False)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/telemetry/events", json=_batch(session_id, [_event()]))
        assert response.status_code == 202
        assert response.json() == {"accepted": 0, "dropped": 0}
        async with SessionLocal() as db:
            session = await db.get(AnalyticsSession, uuid.UUID(session_id))
        assert session is None
    finally:
        await _cleanup_session(session_id)


async def test_emit_is_authoritative_and_never_raises_on_unknown_names() -> None:
    email = f"emit-{uuid.uuid4().hex[:10]}@example.com"
    async with SessionLocal() as db:
        user = User(email=email, full_name="Emit Owner", password_hash="x")
        db.add(user)
        await db.commit()
        try:
            emit(db, "user.registered", user=user, properties={"method": "password", "password": "hunter2"})
            emit(db, "not.registered", user=user)
            await db.commit()
            events = (
                await db.execute(
                    select(AnalyticsEvent).where(AnalyticsEvent.user_id == user.id)
                )
            ).scalars().all()
            assert [event.name for event in events] == ["user.registered"]
            assert events[0].source == "api"
            assert events[0].context == {"authoritative": True}
            assert "hunter2" not in str(events[0].properties)
        finally:
            await db.execute(delete(AnalyticsEvent).where(AnalyticsEvent.user_id == user.id))
            await db.delete(user)
            await db.commit()


async def test_signup_path_emits_authoritative_milestones() -> None:
    email = f"milestones-{uuid.uuid4().hex[:10]}@example.com"
    workspace, _ = await _create_workspace(email)
    company_id = workspace["company"]["id"]
    try:
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(AnalyticsEvent.name, AnalyticsEvent.source).where(
                        AnalyticsEvent.user_id.in_(select(User.id).where(User.email == email))
                    )
                )
            ).all()
        names = {row.name for row in rows}
        assert {"user.registered", "user.email_verified", "user.logged_in", "workspace.created", "plan.selected"} <= names
        assert all(row.source == "api" for row in rows)
    finally:
        await _cleanup_workspace(email, company_id)


async def test_rollups_aggregate_events_by_day_and_route() -> None:
    session_id = str(uuid.uuid4())
    route_key = f"test-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/v1/telemetry/events",
                json=_batch(
                    session_id,
                    [_event("page.viewed", route_key=route_key), _event("page.viewed", route_key=route_key)],
                ),
            )
        async with SessionLocal() as db:
            await rebuild_rollups(db, days=1)
            await db.commit()
            events = await db.scalar(
                text(
                    "SELECT events FROM analytics_daily_rollups "
                    "WHERE route_key = :route_key AND name = 'page.viewed'"
                ),
                {"route_key": route_key},
            )
        assert events == 2
    finally:
        await _cleanup_session(session_id)


def test_route_normalization_drops_query_fragment_and_ids() -> None:
    assert normalize_route("/reset-password?token=SECRET#frag") == "/reset-password"
    assert normalize_route("/0b6c2f1a-8f43-4c2e-9f4f-8f0f7a1b2c3d/setup/plan") == "/:id/setup/plan"
    assert normalize_route("/order/0123456789abcdef0123456789abcdef") == "/order/:token"
    assert normalize_route("") is None
