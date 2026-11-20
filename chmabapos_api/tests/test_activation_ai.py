"""Offline and endpoint tests for the activation AI digest.

The provider is never called: model replies are monkeypatched, and the golden
cases exercise the validator, the deterministic fallback and the privacy guards
without touching a network. Endpoint tests use the real cohort funnel and
telemetry collector, so a citation is only accepted if it resolves against the
evidence this database actually produced.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import AIInsight, AIRun, PlatformSetting
from app.services import activation_ai
from app.services.activation_ai import (
    assemble_evidence,
    fallback_digest,
    validate_digest,
)
from tests.test_admin_funnel import cleanup, create_free_workspace, login_headers, promote_to_admin
from tests.test_telemetry import _batch, _event

AI_KEYS = ("ai_provider", "ai_api_key", "ai_model", "ai_base_url")


# ---------------------------------------------------------------------------
# Fixtures: a clear friction case and a quiet one, used by the golden tests.
# ---------------------------------------------------------------------------


def _funnel() -> dict:
    return {
        "window_days": 30,
        "cohort": "companies",
        "total": 100,
        "stages": [
            {"key": "account_created", "label": "Account created", "count": 100, "from_previous": None, "from_start": 1.0, "median_seconds": 0.0, "p90_seconds": 0.0, "stalled": 0},
            {"key": "email_verified", "label": "Email verified", "count": 95, "from_previous": 0.95, "from_start": 0.95, "median_seconds": 120.0, "p90_seconds": 600.0, "stalled": 5},
            {"key": "first_login", "label": "First sign-in", "count": 90, "from_previous": 0.9474, "from_start": 0.9, "median_seconds": 140.0, "p90_seconds": 700.0, "stalled": 10},
            {"key": "setup_opened", "label": "Setup opened", "count": 80, "from_previous": 0.8889, "from_start": 0.8, "median_seconds": 300.0, "p90_seconds": 900.0, "stalled": 20},
            {"key": "workspace_created", "label": "Workspace created", "count": 50, "from_previous": 0.625, "from_start": 0.5, "median_seconds": 600.0, "p90_seconds": 1204.0, "stalled": 50},
            {"key": "first_product", "label": "Added first product", "count": 40, "from_previous": 0.8, "from_start": 0.4, "median_seconds": 1800.0, "p90_seconds": 4000.0, "stalled": 60},
            {"key": "shift_opened", "label": "Opened a shift", "count": 34, "from_previous": 0.85, "from_start": 0.34, "median_seconds": 2400.0, "p90_seconds": 5000.0, "stalled": 66},
            {"key": "first_sale", "label": "Made first sale", "count": 29, "from_previous": 0.8529, "from_start": 0.29, "median_seconds": 3000.0, "p90_seconds": 6000.0, "stalled": 71},
            {"key": "second_sale", "label": "Made a second sale", "count": 20, "from_previous": 0.6897, "from_start": 0.2, "median_seconds": 9000.0, "p90_seconds": 20000.0, "stalled": 80},
        ],
    }


def _why() -> dict:
    return {
        "workspace_created": {
            "validation_failures": [{"form": "setup", "field": "currency", "rule": "unsupported", "count": 31}],
            "network_failures": [{"route_key": "setup.plan", "endpoint_key": "workspaces.setup", "status": "500", "count": 12}],
            "dead_clicks": [{"element_key": "setup.plan.continue", "count": 27}],
            "rage_clicks": [{"element_key": "setup.plan.continue", "count": 6}],
            "survey": [
                {"answer": "expensive", "count": 9},
                {"answer": "Which numbers do you want?", "count": 4},
            ],
            "dwell": {"median_ms": 6000.0, "p90_ms": 12040.0, "samples": 12},
            "sample_events": 84,
            "sample_sessions": 9,
        },
        "first_product": {
            "validation_failures": [{"form": "product", "field": "price", "rule": "required", "count": 14}],
            "network_failures": [],
            "dead_clicks": [],
            "rage_clicks": [],
            "survey": [],
            "dwell": {"median_ms": 1000.0, "p90_ms": 4000.0, "samples": 5},
            "sample_events": 20,
            "sample_sessions": 3,
        },
    }


def _evidence(funnel: dict | None = None, why: dict | None = None) -> dict:
    start = datetime(2026, 10, 21, tzinfo=timezone.utc)
    return assemble_evidence(
        funnel=funnel or _funnel(),
        why_by_stage=why if why is not None else _why(),
        window_days=30,
        window_start=start,
        window_end=start + timedelta(days=30),
        event_count=812,
    )


def _ids(evidence: dict) -> set[str]:
    return {item["id"] for item in evidence["evidence"]}


# ---------------------------------------------------------------------------
# Unit: evidence ids are deterministic, registry-shaped and private.
# ---------------------------------------------------------------------------


def test_evidence_ids_are_deterministic_and_registry_shaped() -> None:
    first = _evidence()
    second = _evidence()
    assert first["input_hash"] == second["input_hash"]
    assert [item["id"] for item in first["evidence"]] == [item["id"] for item in second["evidence"]]

    ids = _ids(first)
    assert "stage:workspace_created:count" in ids
    assert "stage:workspace_created:from_previous" in ids
    assert "stage:workspace_created:from_previous_pct" in ids
    assert "why:workspace_created:validation:setup.currency.unsupported" in ids
    assert "why:workspace_created:network:workspaces.setup:500" in ids
    assert "why:workspace_created:dead:setup.plan.continue" in ids
    assert "why:workspace_created:survey:expensive" in ids
    assert "why:workspace_created:survey:other" in ids
    assert "why:workspace_created:dwell:p90" in ids
    # A stage with no diagnostic routes is never cited.
    assert not any("second_sale" in evidence_id for evidence_id in ids)


def test_free_text_and_user_ids_never_enter_the_evidence() -> None:
    why = _why()
    why["workspace_created"]["survey"] = [
        {"answer": "My name is Dara, call 012345678", "count": 3},
        {"answer": "expensive", "count": 2},
    ]
    why["workspace_created"]["dead_clicks"] = [
        {"element_key": "email me at dara@example.com", "count": 2},
        {"element_key": "setup.plan.continue", "count": 1},
    ]
    evidence = _evidence(why=why)
    serialized = json.dumps(evidence)
    assert "Dara" not in serialized
    assert "012345678" not in serialized
    assert "dara@example.com" not in serialized
    assert "why:workspace_created:survey:other" in _ids(evidence)
    assert "why:workspace_created:survey:expensive" in _ids(evidence)
    # The unsafe element key is dropped, the registry key survives.
    assert "why:workspace_created:dead:setup.plan.continue" in _ids(evidence)
    assert not any("email" in evidence_id for evidence_id in _ids(evidence))


def test_validator_rejects_uncited_finding() -> None:
    evidence = _evidence()
    reply = json.dumps(
        {
            "headline": "Workspace setup leaks",
            "findings": [
                {
                    "stage": "workspace_created",
                    "severity": "high",
                    "claim": "The setup plan step is the sink.",
                    "evidence": [],
                    "confidence": 0.8,
                }
            ],
            "recommended_focus": "workspace_created",
            "insufficient_evidence": False,
        }
    )
    result = validate_digest(reply, evidence)
    assert result.ok is False
    assert "cites no evidence" in (result.error or "")


def test_validator_rejects_unknown_stage_and_unknown_evidence() -> None:
    evidence = _evidence()
    base = {
        "headline": "Workspace setup leaks",
        "findings": [],
        "recommended_focus": "",
        "insufficient_evidence": False,
    }
    unknown_stage = {
        **base,
        "findings": [
            {
                "stage": "not_a_stage",
                "severity": "high",
                "claim": "Something is wrong.",
                "evidence": ["stage:workspace_created:count"],
                "confidence": 0.8,
            }
        ],
    }
    assert validate_digest(json.dumps(unknown_stage), evidence).ok is False

    unknown_id = {
        **base,
        "findings": [
            {
                "stage": "workspace_created",
                "severity": "high",
                "claim": "Something is wrong.",
                "evidence": ["error:made.up"],
                "confidence": 0.8,
            }
        ],
    }
    result = validate_digest(json.dumps(unknown_id), evidence)
    assert result.ok is False
    assert "not in the input" in (result.error or "")


def test_validator_rejects_invented_numbers_and_non_json() -> None:
    evidence = _evidence()
    invented = {
        "headline": "Workspace setup leaks",
        "findings": [
            {
                "stage": "workspace_created",
                "severity": "high",
                "claim": "73% of merchants saw the plan step fail.",
                "evidence": ["why:workspace_created:validation:setup.currency.unsupported"],
                "confidence": 0.8,
            }
        ],
        "recommended_focus": "workspace_created",
        "insufficient_evidence": False,
    }
    result = validate_digest(json.dumps(invented), evidence)
    assert result.ok is False
    assert "number" in (result.error or "")
    assert validate_digest("the provider timed out", evidence).ok is False


def test_validator_accepts_a_cited_reply() -> None:
    evidence = _evidence()
    reply = json.dumps(
        {
            "headline": "Workspace setup loses the cohort",
            "findings": [
                {
                    "stage": "workspace_created",
                    "severity": "high",
                    "claim": "62.5% of the previous stage continued; 31 validation failures on setup.currency (unsupported).",
                    "evidence": [
                        "stage:workspace_created:from_previous_pct",
                        "why:workspace_created:validation:setup.currency.unsupported",
                    ],
                    "confidence": 0.82,
                }
            ],
            "recommended_focus": "workspace_created",
            "insufficient_evidence": False,
        }
    )
    result = validate_digest(reply, evidence)
    assert result.ok is True, result.error


# ---------------------------------------------------------------------------
# Golden fixtures (offline): clear friction, no signal, provider failure.
# ---------------------------------------------------------------------------


def test_golden_clear_friction_case() -> None:
    evidence = _evidence()
    payload = fallback_digest(evidence)
    result = validate_digest(json.dumps(payload), evidence)
    assert result.ok is True, result.error
    assert payload["findings"], "a clear drop must produce a finding"
    assert payload["recommended_focus"] == "workspace_created"
    assert payload["findings"][0]["severity"] in {"medium", "high"}
    assert payload["findings"][0]["stage"] == "workspace_created"
    cited = {item for finding in payload["findings"] for item in finding["evidence"]}
    assert cited <= _ids(evidence)


def test_golden_no_signal_case() -> None:
    quiet = _funnel()
    for stage in quiet["stages"]:
        if stage["from_previous"] is not None:
            stage["from_previous"] = 0.99
        stage["p90_seconds"] = 60.0
    evidence = assemble_evidence(
        funnel=quiet,
        why_by_stage={},
        window_days=30,
        window_start=datetime(2026, 10, 21, tzinfo=timezone.utc),
        window_end=datetime(2026, 11, 20, tzinfo=timezone.utc),
        event_count=500,
    )
    payload = fallback_digest(evidence)
    result = validate_digest(json.dumps(payload), evidence)
    assert result.ok is True, result.error
    assert payload["findings"] == []
    assert payload["recommended_focus"] == ""
    assert "No stage shows material friction" in payload["headline"]
    assert payload["insufficient_evidence"] is False


def test_golden_provider_failure_case_falls_back_to_rules() -> None:
    evidence = _evidence()
    # A provider failure or an unreadable reply is not a finding.
    assert validate_digest("", evidence).ok is False
    payload = fallback_digest(evidence)
    result = validate_digest(json.dumps(payload), evidence)
    assert result.ok is True, result.error
    assert all(finding["evidence"] for finding in payload["findings"])
    assert all(set(finding["evidence"]) <= _ids(evidence) for finding in payload["findings"])


def test_insufficient_evidence_skips_the_why_queries_and_the_provider() -> None:
    empty = assemble_evidence(
        funnel={"window_days": 30, "cohort": "companies", "total": 0, "stages": []},
        why_by_stage={},
        window_days=30,
        window_start=datetime(2026, 10, 21, tzinfo=timezone.utc),
        window_end=datetime(2026, 11, 20, tzinfo=timezone.utc),
        event_count=0,
    )
    assert empty["insufficient"] is True
    assert empty["stages"] == []
    assert "No workspaces" in empty["insufficient_reason"]

    thin = assemble_evidence(
        funnel=_funnel(),
        why_by_stage={},
        window_days=30,
        window_start=datetime(2026, 10, 21, tzinfo=timezone.utc),
        window_end=datetime(2026, 11, 20, tzinfo=timezone.utc),
        event_count=7,
    )
    assert thin["insufficient"] is True
    assert "7 telemetry events" in thin["insufficient_reason"]


# ---------------------------------------------------------------------------
# Endpoint helpers
# ---------------------------------------------------------------------------


async def _new_workspace(client: AsyncClient, prefix: str) -> tuple[str, dict, dict]:
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    workspace, headers = await create_free_workspace(client, email)
    return email, workspace, headers


async def _seed_friction(client: AsyncClient, headers: dict) -> str:
    events = []
    for index in range(5):
        events.append(
            _event(
                "ui.form_validation_failed",
                {"form": "signup", "field": "email", "rule": "required"},
                route_key="signup",
            )
        )
        events.append(
            _event(
                "error.network",
                {"endpoint_key": "auth.register", "status": 500, "error_code": "server"},
                route_key="signup",
            )
        )
        events.append(
            _event("ui.dead_click", {"route_key": "signup"}, route_key="signup", element_key="signup.submit")
        )
        events.append(
            _event("page.left", {"dwell_ms": 4000 + index * 1000, "scroll_pct": 40}, route_key="signup")
        )
        events.append(
            _event(
                "onboarding.abandon_survey",
                {"step_key": "Choose your plan", "answer": "expensive" if index % 2 else "unclear"},
                route_key="setup.plan",
            )
        )
    session_id = str(uuid.uuid4())
    response = await client.post("/api/v1/telemetry/events", headers=headers, json=_batch(session_id, events))
    assert response.status_code == 202, response.text
    assert response.json()["accepted"] == 25, response.text
    return session_id


async def _set_ai_settings(configured: bool) -> None:
    async with SessionLocal() as db:
        await db.execute(
            text("DELETE FROM platform_settings WHERE key = ANY(CAST(:keys AS text[]))"),
            {"keys": list(AI_KEYS)},
        )
        if configured:
            db.add(PlatformSetting(key="ai_provider", value="openai"))
            db.add(PlatformSetting(key="ai_api_key", value="sk-test"))
        await db.commit()


async def _user_id(email: str) -> uuid.UUID:
    async with SessionLocal() as db:
        return (await db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email})).scalar_one()


async def _purge_digests(days: int) -> None:
    async with SessionLocal() as db:
        await db.execute(
            text(
                "DELETE FROM ai_runs WHERE insight_id IN "
                "(SELECT id FROM ai_insights WHERE window_days = :days)"
            ),
            {"days": days},
        )
        await db.execute(text("DELETE FROM ai_insights WHERE window_days = :days"), {"days": days})
        await db.commit()


async def _purge_analytics(email: str, company_id: str | None) -> None:
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


def _fake_reply(evidence_document: dict) -> str:
    stage = evidence_document["stages"][0]
    return json.dumps(
        {
            "headline": f"{stage['label']} is where the cohort stalls",
            "findings": [
                {
                    "stage": stage["key"],
                    "severity": "high",
                    "claim": "The stage loses most of the cohort before the next milestone.",
                    "evidence": [
                        stage["metrics"]["reached"]["id"],
                        stage["metrics"]["stalled"]["id"],
                    ],
                    "confidence": 0.8,
                }
            ],
            "recommended_focus": stage["key"],
            "insufficient_evidence": False,
        }
    )


def _patch_fake_provider(monkeypatch: pytest.MonkeyPatch, calls: list[dict]) -> None:
    async def fake_complete_chat(db, *, system, messages, temperature=0.3, max_tokens=900):
        calls.append({"system": system, "messages": messages, "temperature": temperature, "max_tokens": max_tokens})
        document = json.loads(messages[0]["content"])
        return {
            "content": _fake_reply(document),
            "provider": "openai",
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 120, "completion_tokens": 60},
        }

    monkeypatch.setattr(activation_ai, "complete_chat", fake_complete_chat)


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


async def test_digest_run_stores_a_cited_insight_and_accepts_a_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    days = 377
    merchant_email = admin_email = ""
    merchant_company = admin_company = None
    calls: list[dict] = []
    try:
        await _set_ai_settings(True)
        await _purge_digests(days)
        _patch_fake_provider(monkeypatch, calls)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            merchant_email, merchant_workspace, merchant_headers = await _new_workspace(client, "digest-ok")
            merchant_company = merchant_workspace["company"]["id"]
            await _seed_friction(client, merchant_headers)

            admin_email, admin_workspace, _ = await _new_workspace(client, "digest-ok-admin")
            admin_company = admin_workspace["company"]["id"]
            await promote_to_admin(admin_email)
            admin_headers = await login_headers(client, admin_email)
            admin_id = await _user_id(admin_email)

            before = await client.get(
                "/api/v1/admin/journeys/digest", headers=admin_headers, params={"days": days}
            )
            assert before.status_code == 200
            assert before.json() is None

            created = await client.post(
                "/api/v1/admin/journeys/digest/run", headers=admin_headers, params={"days": days}
            )
            assert created.status_code == 200, created.text
            body = created.json()
            assert body["validator"] == "passed"
            assert body["provider"] == "openai"
            assert body["model"] == "gpt-4o-mini"
            assert body["prompt_version"] == activation_ai.PROMPT_VERSION
            assert body["decision"] is None
            assert body["evidence"], "the stored insight must keep the evidence document"
            allowed = {item["id"] for item in body["evidence"]}
            assert body["payload"]["findings"]
            for finding in body["payload"]["findings"]:
                assert finding["evidence"]
                assert set(finding["evidence"]) <= allowed
            assert body["stage_key"] in {item["stage"] for item in body["evidence"] if item["stage"]}

            latest = await client.get(
                "/api/v1/admin/journeys/digest", headers=admin_headers, params={"days": days}
            )
            assert latest.status_code == 200, latest.text
            assert latest.json()["id"] == body["id"]

            decided = await client.patch(
                f"/api/v1/admin/journeys/digest/{body['id']}/decision",
                headers=admin_headers,
                json={"decision": "accepted", "note": "Matches the session drilldown."},
            )
            assert decided.status_code == 200, decided.text
            decision = decided.json()
            assert decision["decision"] == "accepted"
            assert decision["decided_by"] == str(admin_id)
            assert decision["decision_note"] == "Matches the session drilldown."
            assert decision["decided_at"] is not None

            missing = await client.patch(
                f"/api/v1/admin/journeys/digest/{uuid.uuid4()}/decision",
                headers=admin_headers,
                json={"decision": "rejected"},
            )
            assert missing.status_code == 404

        async with SessionLocal() as db:
            insight = await db.get(AIInsight, uuid.UUID(body["id"]))
            assert insight is not None
            assert insight.validator == "passed"
            assert insight.input_hash
            assert insight.decision == "accepted"
            runs = (
                await db.execute(select(AIRun).where(AIRun.insight_id == insight.id))
            ).scalars().all()
            assert len(runs) == 1
            assert runs[0].outcome == "ok"
            assert runs[0].prompt_tokens == 120
            assert runs[0].completion_tokens == 60
            assert runs[0].cost_usd is not None and float(runs[0].cost_usd) > 0
        assert len(calls) == 1
        assert calls[0]["temperature"] == 0.2
        assert calls[0]["max_tokens"] == 900
    finally:
        await _set_ai_settings(False)
        await _purge_digests(days)
        if merchant_email:
            await _purge_analytics(merchant_email, merchant_company)
            await cleanup(merchant_email, merchant_company)
        if admin_email:
            await _purge_analytics(admin_email, admin_company)
            await cleanup(admin_email, admin_company)


async def test_digest_falls_back_when_the_model_replies_with_garbage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    days = 378
    merchant_email = admin_email = ""
    merchant_company = admin_company = None
    calls: list[int] = []
    try:
        await _set_ai_settings(True)
        await _purge_digests(days)

        async def garbage(db, *, system, messages, temperature=0.3, max_tokens=900):
            calls.append(1)
            return {"content": "not json", "provider": "openai", "model": "gpt-4o-mini", "usage": {"prompt_tokens": 10, "completion_tokens": 2}}

        monkeypatch.setattr(activation_ai, "complete_chat", garbage)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            merchant_email, merchant_workspace, merchant_headers = await _new_workspace(client, "digest-fallback")
            merchant_company = merchant_workspace["company"]["id"]
            await _seed_friction(client, merchant_headers)
            admin_email, admin_workspace, _ = await _new_workspace(client, "digest-fallback-admin")
            admin_company = admin_workspace["company"]["id"]
            await promote_to_admin(admin_email)
            admin_headers = await login_headers(client, admin_email)

            created = await client.post(
                "/api/v1/admin/journeys/digest/run", headers=admin_headers, params={"days": days}
            )
            assert created.status_code == 200, created.text
            body = created.json()

        assert len(calls) == 2, "one retry, then deterministic fallback"
        assert body["validator"] == "fallback"
        assert body["payload"]["insufficient_evidence"] is False
        allowed = {item["id"] for item in body["evidence"]}
        for finding in body["payload"]["findings"]:
            assert finding["evidence"]
            assert set(finding["evidence"]) <= allowed
        async with SessionLocal() as db:
            runs = (
                await db.execute(select(AIRun).where(AIRun.insight_id == uuid.UUID(body["id"])))
            ).scalars().all()
            assert [run.outcome for run in runs] == ["parse_error", "parse_error"]
    finally:
        await _set_ai_settings(False)
        await _purge_digests(days)
        if merchant_email:
            await _purge_analytics(merchant_email, merchant_company)
            await cleanup(merchant_email, merchant_company)
        if admin_email:
            await _purge_analytics(admin_email, admin_company)
            await cleanup(admin_email, admin_company)


async def test_digest_falls_back_when_the_provider_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    days = 379
    merchant_email = admin_email = ""
    merchant_company = admin_company = None
    try:
        await _set_ai_settings(True)
        await _purge_digests(days)

        async def broken(db, *, system, messages, temperature=0.3, max_tokens=900):
            raise activation_ai.AIError("provider down")

        monkeypatch.setattr(activation_ai, "complete_chat", broken)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            merchant_email, merchant_workspace, merchant_headers = await _new_workspace(client, "digest-down")
            merchant_company = merchant_workspace["company"]["id"]
            await _seed_friction(client, merchant_headers)
            admin_email, admin_workspace, _ = await _new_workspace(client, "digest-down-admin")
            admin_company = admin_workspace["company"]["id"]
            await promote_to_admin(admin_email)
            admin_headers = await login_headers(client, admin_email)

            created = await client.post(
                "/api/v1/admin/journeys/digest/run", headers=admin_headers, params={"days": days}
            )
            assert created.status_code == 200, created.text
            body = created.json()

        assert body["validator"] == "fallback"
        async with SessionLocal() as db:
            runs = (
                await db.execute(select(AIRun).where(AIRun.insight_id == uuid.UUID(body["id"])))
            ).scalars().all()
            assert [run.outcome for run in runs] == ["provider_error"]
    finally:
        await _set_ai_settings(False)
        await _purge_digests(days)
        if merchant_email:
            await _purge_analytics(merchant_email, merchant_company)
            await cleanup(merchant_email, merchant_company)
        if admin_email:
            await _purge_analytics(admin_email, admin_company)
            await cleanup(admin_email, admin_company)


async def test_digest_returns_400_when_ai_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    days = 381
    merchant_email = admin_email = ""
    merchant_company = admin_company = None
    try:
        await _set_ai_settings(False)

        async def must_not_run(db, *, system, messages, temperature=0.3, max_tokens=900):
            raise AssertionError("the provider must not be called without configuration")

        monkeypatch.setattr(activation_ai, "complete_chat", must_not_run)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            merchant_email, merchant_workspace, merchant_headers = await _new_workspace(client, "digest-noconfig")
            merchant_company = merchant_workspace["company"]["id"]
            await _seed_friction(client, merchant_headers)
            admin_email, admin_workspace, _ = await _new_workspace(client, "digest-noconfig-admin")
            admin_company = admin_workspace["company"]["id"]
            await promote_to_admin(admin_email)
            admin_headers = await login_headers(client, admin_email)

            response = await client.post(
                "/api/v1/admin/journeys/digest/run", headers=admin_headers, params={"days": days}
            )
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "Configure AI in Settings > AI writing"
    finally:
        await _set_ai_settings(False)
        await _purge_digests(days)
        if merchant_email:
            await _purge_analytics(merchant_email, merchant_company)
            await cleanup(merchant_email, merchant_company)
        if admin_email:
            await _purge_analytics(admin_email, admin_company)
            await cleanup(admin_email, admin_company)


async def test_digest_returns_503_when_the_kill_switch_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    days = 382
    merchant_email = admin_email = ""
    merchant_company = admin_company = None
    try:
        await _set_ai_settings(True)
        monkeypatch.setattr(activation_ai.settings, "activation_ai_enabled", False)

        async def must_not_run(db, *, system, messages, temperature=0.3, max_tokens=900):
            raise AssertionError("the provider must not be called while disabled")

        monkeypatch.setattr(activation_ai, "complete_chat", must_not_run)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_email, admin_workspace, _ = await _new_workspace(client, "digest-off-admin")
            admin_company = admin_workspace["company"]["id"]
            await promote_to_admin(admin_email)
            admin_headers = await login_headers(client, admin_email)
            response = await client.post(
                "/api/v1/admin/journeys/digest/run", headers=admin_headers, params={"days": days}
            )
        assert response.status_code == 503, response.text
        assert "disabled" in response.json()["detail"].lower()
    finally:
        await _set_ai_settings(False)
        if merchant_email:
            await _purge_analytics(merchant_email, merchant_company)
            await cleanup(merchant_email, merchant_company)
        if admin_email:
            await _purge_analytics(admin_email, admin_company)
            await cleanup(admin_email, admin_company)


async def test_digest_insufficient_evidence_never_calls_the_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    days = 380
    merchant_email = admin_email = ""
    merchant_company = admin_company = None
    try:
        await _set_ai_settings(True)
        await _purge_digests(days)

        async def must_not_run(db, *, system, messages, temperature=0.3, max_tokens=900):
            raise AssertionError("an empty window must not reach a provider")

        monkeypatch.setattr(activation_ai, "complete_chat", must_not_run)

        async def empty_funnel(db, *, days=30):
            return {"window_days": days, "cohort": "companies", "total": 0, "stages": []}

        monkeypatch.setattr(activation_ai, "build_funnel", empty_funnel)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_email, admin_workspace, _ = await _new_workspace(client, "digest-empty-admin")
            admin_company = admin_workspace["company"]["id"]
            await promote_to_admin(admin_email)
            admin_headers = await login_headers(client, admin_email)
            created = await client.post(
                "/api/v1/admin/journeys/digest/run", headers=admin_headers, params={"days": days}
            )
            assert created.status_code == 200, created.text
            body = created.json()

        assert body["validator"] == "insufficient"
        assert body["payload"]["insufficient_evidence"] is True
        assert body["payload"]["findings"] == []
        assert body["provider"] is None and body["model"] is None
        assert {item["id"] for item in body["evidence"]} <= {"cohort:total", "cohort:events"}
        async with SessionLocal() as db:
            runs = (
                await db.execute(select(AIRun).where(AIRun.insight_id == uuid.UUID(body["id"])))
            ).scalars().all()
            assert runs == []
    finally:
        await _set_ai_settings(False)
        await _purge_digests(days)
        if merchant_email:
            await _purge_analytics(merchant_email, merchant_company)
            await cleanup(merchant_email, merchant_company)
        if admin_email:
            await _purge_analytics(admin_email, admin_company)
            await cleanup(admin_email, admin_company)


async def test_digest_endpoints_are_platform_admin_only() -> None:
    email = f"digest-denied-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            denied_run = await client.post("/api/v1/admin/journeys/digest/run", headers=headers)
            denied_read = await client.get("/api/v1/admin/journeys/digest", headers=headers)
            denied_decision = await client.patch(
                f"/api/v1/admin/journeys/digest/{uuid.uuid4()}/decision",
                headers=headers,
                json={"decision": "accepted"},
            )
        assert denied_run.status_code == 403
        assert denied_read.status_code == 403
        assert denied_decision.status_code == 403
    finally:
        await _purge_analytics(email, company_id)
        await cleanup(email, company_id)
