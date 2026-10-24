"""Platform self-monitoring: probe state, transitions, alerting and the admin API."""
from __future__ import annotations

import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import SystemHealthCheck, SystemHealthEvent
from app.services import health as health_service


def _check(name: str, *, severity: str = "critical", result=None):
    """A probe that always returns ``result`` (or reads it from ``results``)."""

    async def probe(db):  # noqa: ANN001 - matches the probe signature
        return result

    return health_service.Check(name=name, label=name.replace("_", " ").title(), category="test", severity=severity, probe=probe)


async def _clear_health_tables() -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM system_health_events"))
        await db.execute(text("DELETE FROM system_health_checks"))
        await db.commit()


@pytest.fixture(autouse=True)
async def _isolate_health_tables():
    await _clear_health_tables()
    health_service.reset_khqr_signals()
    yield
    await _clear_health_tables()
    health_service.reset_khqr_signals()


def test_checks_cover_the_platform() -> None:
    names = [check.name for check in health_service.CHECKS]
    assert len(names) == len(set(names))
    for required in ("database", "khqr_generation", "email_outbound", "media_storage"):
        assert required in names
    assert {check.severity for check in health_service.CHECKS} <= {"critical", "warning", "info"}


def test_link_tally_mirrors_the_checkout_rule() -> None:
    stores = [
        SimpleNamespace(id=uuid.uuid4(), name="Good Shop", aba_payway_links={"USD": {"link": "https://pay/x", "status": "active"}}),
        SimpleNamespace(id=uuid.uuid4(), name="Broken Shop", aba_payway_links={"KHR": {"link": "https://pay/y", "status": "error"}}),
        SimpleNamespace(id=uuid.uuid4(), name="Pending Shop", aba_payway_links={"USD": {"link": "https://pay/z", "status": "pending"}}),
        SimpleNamespace(id=uuid.uuid4(), name="No Link Shop", aba_payway_links=None),
    ]
    tally = health_service._link_tally(stores)
    assert tally["active"] == 1
    assert tally["error"] == 1
    assert tally["pending"] == 1
    assert tally["objects"] == 3
    assert "Broken Shop (KHR)" in tally["problems"]


@pytest.mark.asyncio
async def test_run_checks_records_state_alerts_once_and_announces_recovery(monkeypatch) -> None:
    results = {"flaky": health_service.CheckResult(health_service.STATUS_DOWN, "Provider unreachable")}
    sent: list[str] = []

    async def fake_send(message: str) -> bool:
        sent.append(message)
        return True

    monkeypatch.setattr(health_service, "send_telegram_message", fake_send)
    monkeypatch.setattr(settings, "health_check_alert_after_failures", 2)
    monkeypatch.setattr(settings, "health_check_alert_cooldown_minutes", 30)
    monkeypatch.setattr(
        health_service,
        "CHECKS",
        (
            _check("database", result=health_service.CheckResult(health_service.STATUS_OK, "fine")),
            health_service.Check(
                name="flaky",
                label="Flaky check",
                category="test",
                severity="critical",
                probe=lambda db: _result_of(results),
            ),
        ),
    )

    async with SessionLocal() as db:
        first = await health_service.run_checks(db)
    assert first["overall_status"] == health_service.STATUS_DOWN
    flaky = next(check for check in first["checks"] if check["name"] == "flaky")
    assert flaky["consecutive_failures"] == 1
    assert sent == []  # one bad sweep is not worth a page

    async with SessionLocal() as db:
        second = await health_service.run_checks(db)
    flaky = next(check for check in second["checks"] if check["name"] == "flaky")
    assert flaky["consecutive_failures"] == 2
    assert len(sent) == 1
    assert "Flaky check is down" in sent[0]

    # A third bad sweep inside the cooldown must not page again.
    async with SessionLocal() as db:
        third = await health_service.run_checks(db)
    assert len(sent) == 1
    flaky = next(check for check in third["checks"] if check["name"] == "flaky")
    assert flaky["consecutive_failures"] == 3

    results["flaky"] = health_service.CheckResult(health_service.STATUS_OK, "Recovered")
    async with SessionLocal() as db:
        recovered = await health_service.run_checks(db)
    assert recovered["overall_status"] == health_service.STATUS_OK
    assert len(sent) == 2
    assert "Chmaba recovered" in sent[1]

    async with SessionLocal() as db:
        events = (await db.execute(select(SystemHealthEvent).order_by(SystemHealthEvent.created_at))).scalars().all()
    transitions = [(event.previous_status, event.status) for event in events if event.check_name == "flaky"]
    assert (None, health_service.STATUS_DOWN) in transitions
    assert (health_service.STATUS_DOWN, health_service.STATUS_OK) in transitions


async def _result_of(results: dict):
    return results["flaky"]


@pytest.mark.asyncio
async def test_manual_run_never_pages(monkeypatch) -> None:
    sent: list[str] = []

    async def fake_send(message: str) -> bool:
        sent.append(message)
        return True

    monkeypatch.setattr(health_service, "send_telegram_message", fake_send)
    monkeypatch.setattr(settings, "health_check_alert_after_failures", 1)
    monkeypatch.setattr(
        health_service,
        "CHECKS",
        (_check("down_check", result=health_service.CheckResult(health_service.STATUS_DOWN, "broken")),),
    )

    async with SessionLocal() as db:
        state = await health_service.run_checks(db, trigger="manual")
    assert state["overall_status"] == health_service.STATUS_DOWN
    assert state["checks"][0]["consecutive_failures"] == 1
    assert sent == []


@pytest.mark.asyncio
async def test_khqr_check_is_skipped_in_mock_mode(monkeypatch) -> None:
    async def fake_settings(db):
        return {"chamabapay_mode": "mock", "chamabapay_api_key": "", "chamabapay_api_url": ""}

    monkeypatch.setattr(health_service, "load_payment_settings", fake_settings)
    async with SessionLocal() as db:
        result = await health_service._probe_khqr_generation(db)
    assert result.status == health_service.STATUS_SKIPPED
    assert "mock" in result.summary.lower()


@pytest.mark.asyncio
async def test_khqr_check_is_down_without_an_active_merchant_link(monkeypatch) -> None:
    async def fake_settings(db):
        return {"chamabapay_mode": "live", "chamabapay_api_key": "key", "chamabapay_api_url": "https://pay.test/api"}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def list_stores(self):
            return [{"id": "st_1"}]

    async def fake_links(db):
        return {"active": 0, "error": 0, "pending": 1, "none": 0, "configured": 1, "objects": 1, "problems": []}

    monkeypatch.setattr(health_service, "load_payment_settings", fake_settings)
    monkeypatch.setattr(health_service, "ChmabaPayClient", FakeClient)
    monkeypatch.setattr(health_service, "_platform_links", fake_links)

    async with SessionLocal() as db:
        result = await health_service._probe_khqr_generation(db)
    assert result.status == health_service.STATUS_DOWN
    assert "active KHQR link" in result.summary


@pytest.mark.asyncio
async def test_khqr_check_surfaces_failures_the_provider_cannot_report(monkeypatch) -> None:
    """The whole point: a cashier's failed QR turns the platform red."""

    async def fake_settings(db):
        return {"chamabapay_mode": "live", "chamabapay_api_key": "key", "chamabapay_api_url": "https://pay.test/api"}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def list_stores(self):
            return [{"id": "st_1"}]

    async def fake_links(db):
        return {"active": 2, "error": 0, "pending": 0, "none": 0, "configured": 2, "objects": 1, "problems": []}

    monkeypatch.setattr(health_service, "load_payment_settings", fake_settings)
    monkeypatch.setattr(health_service, "ChmabaPayClient", FakeClient)
    monkeypatch.setattr(health_service, "_platform_links", fake_links)

    health_service.record_khqr_failure("ChmabaPay request failed (502)")
    async with SessionLocal() as db:
        degraded = await health_service._probe_khqr_generation(db)
    assert degraded.status == health_service.STATUS_DEGRADED

    health_service.record_khqr_failure("ChmabaPay request failed (502)")
    async with SessionLocal() as db:
        down = await health_service._probe_khqr_generation(db)
    assert down.status == health_service.STATUS_DOWN
    assert "2 KHQR requests failed" in down.summary
    assert "502" in (down.detail or "")


@pytest.mark.asyncio
async def test_health_endpoint_reports_dependency_counts() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["database"] == "connected"
        assert response.json()["dependencies"]["overall"] == health_service.STATUS_UNKNOWN

        async with SessionLocal() as db:
            db.add(
                SystemHealthCheck(
                    name="khqr_generation",
                    label="KHQR checkout",
                    category="payments",
                    severity="critical",
                    status=health_service.STATUS_DOWN,
                    summary="No merchant has an active KHQR link",
                    checked_at=health_service.utcnow(),
                    changed_at=health_service.utcnow(),
                )
            )
            await db.commit()

        response = await client.get("/api/v1/health")
        assert response.status_code == 200  # never 503: the container must not restart-loop
        dependencies = response.json()["dependencies"]
        assert dependencies["overall"] == health_service.STATUS_DOWN
        assert dependencies["down"] == 1


async def _create_free_workspace(client: AsyncClient, email: str) -> tuple[dict, dict]:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Health Owner", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Health Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json(), headers


async def _promote(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": email})
        await db.commit()


async def _login_headers(client: AsyncClient, email: str) -> dict:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _cleanup_workspace(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM platform_activities WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        if company_id:
            parameters = {"company_id": company_id}
            for statement in (
                "DELETE FROM subscription_capacity_actions WHERE company_id = :company_id",
                "DELETE FROM billing_refunds WHERE company_id = :company_id",
                "DELETE FROM billing_receipts WHERE company_id = :company_id",
                "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                "DELETE FROM subscriptions WHERE company_id = :company_id",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM invitations WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM categories WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ):
                await db.execute(text(statement), parameters)
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_system_health_requires_platform_admin() -> None:
    email = f"health-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await _create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            denied = await client.get("/api/v1/admin/system-health", headers=headers)
            assert denied.status_code == 403
            denied_run = await client.post("/api/v1/admin/system-health/run", headers=headers)
            assert denied_run.status_code == 403
    finally:
        await _cleanup_workspace(email, company_id)


@pytest.mark.asyncio
async def test_system_health_page_and_run_now(monkeypatch) -> None:
    monkeypatch.setattr(
        health_service,
        "CHECKS",
        (
            _check("database", result=health_service.CheckResult(health_service.STATUS_OK, "Responding in 2 ms", latency_ms=2)),
            _check("khqr_generation", result=health_service.CheckResult(health_service.STATUS_DOWN, "ChmabaPay unreachable")),
        ),
    )
    email = f"health-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, _ = await _create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
        await _promote(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await _login_headers(client, email)
            response = await client.get("/api/v1/admin/system-health", headers=headers)
            assert response.status_code == 200
            assert response.json()["checks"] == []
            assert response.json()["stale"] is True

            run = await client.post("/api/v1/admin/system-health/run", headers=headers)
            assert run.status_code == 200
            data = run.json()
            assert data["overall_status"] == health_service.STATUS_DOWN
            assert data["stale"] is False
            by_name = {check["name"]: check for check in data["checks"]}
            assert by_name["khqr_generation"]["status"] == health_service.STATUS_DOWN
            assert by_name["database"]["latency_ms"] == 2
            assert [event["status"] for event in data["events"]].count(health_service.STATUS_DOWN) == 1

            attention = await client.get("/api/v1/admin/attention", headers=headers)
            assert attention.status_code == 200
            first = attention.json()["items"][0]
            assert first["kind"] == "system_health"
            assert first["count"] == 1
            assert first["page"] == "health"
    finally:
        await _cleanup_workspace(email, company_id)


@pytest.mark.asyncio
async def test_snapshot_marks_a_stale_worker(monkeypatch) -> None:
    monkeypatch.setattr(settings, "health_check_interval_seconds", 120)
    async with SessionLocal() as db:
        db.add(
            SystemHealthCheck(
                name="database",
                label="Database",
                category="infrastructure",
                severity="critical",
                status=health_service.STATUS_OK,
                summary="Responding in 1 ms",
                checked_at=health_service.utcnow() - timedelta(hours=2),
                changed_at=health_service.utcnow() - timedelta(hours=2),
            )
        )
        await db.commit()
        state = await health_service.snapshot(db)
    assert state["stale"] is True
    assert state["overall_status"] == health_service.STATUS_OK
