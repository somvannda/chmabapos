"""Step review: deterministic counts first, AI narrative second, human decision.

The provider is never called here. Model replies are monkeypatched so the tests
exercise the transition matrix, the marginal-conversion formula, the validator,
the deterministic fallback and the draft-experiment endpoints without a network.
"""
from __future__ import annotations

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import AIInsight, AIRun, ActivationExperiment, PlatformSetting
from app.services import step_review_ai
from app.services.step_review import (
    MIN_SESSIONS,
    analyse_step_review,
    marginal_conversion,
    transition_matrix,
)
from app.services.step_review_ai import fallback_step_review, validate_step_review
from tests.test_admin_funnel import cleanup, create_free_workspace, login_headers, promote_to_admin
from tests.test_telemetry import _batch, _event

AI_KEYS = ("ai_provider", "ai_api_key", "ai_model", "ai_base_url")


# ---------------------------------------------------------------------------
# Unit: counting, loops, backtracks, marginal conversion and sufficiency.
# ---------------------------------------------------------------------------


def test_transition_matrix_counts_sessions_not_events() -> None:
    # Each session repeats the same loop five times. The pair A -> B is one
    # transition for each session, not five per session.
    sequences = {
        "s1": ["signup", "setup.company", "setup.questions", "setup.company"] * 5,
        "s2": ["signup", "setup.company", "setup.questions", "setup.company"] * 5,
    }
    transitions, loops, backtracks = transition_matrix(sequences)
    by_pair = {(row["from"], row["to"]): row["sessions"] for row in transitions}
    assert by_pair[("signup", "setup.company")] == 2
    assert by_pair[("setup.company", "setup.questions")] == 2
    assert by_pair[("setup.questions", "setup.company")] == 2
    # Five visits per session, two sessions: still exactly four distinct pairs.
    assert len(transitions) == 4
    assert loops and loops[0]["sessions"] == 2
    assert loops[0]["key"] == "setup.company->setup.questions->setup.company"


def test_loops_and_backtracks_are_detected_per_session() -> None:
    sequences = {
        "s1": ["setup.company", "setup.plan", "setup.company", "setup.plan"],
        "s2": ["setup.company", "setup.plan", "setup.company"],
        "s3": ["setup.company", "setup.questions", "setup.plan"],
    }
    transitions, loops, backtracks = transition_matrix(sequences)
    loop_by_key = {row["key"]: row["sessions"] for row in loops}
    assert loop_by_key["setup.company->setup.plan->setup.company"] == 2
    assert loop_by_key["setup.plan->setup.company->setup.plan"] == 1
    back_by_pair = {(row["from"], row["to"]): row["sessions"] for row in backtracks}
    assert back_by_pair[("setup.plan", "setup.company")] == 2
    assert ("setup.company", "setup.questions") not in back_by_pair
    assert len(transitions) >= 2


def test_unfiltered_route_keys_are_dropped() -> None:
    transitions, loops, backtracks = transition_matrix(
        {
            "s1": ["setup.company", "email me at dara@example.com", "setup.plan"],
            "s2": ["setup.company", "Dara 012345678", "setup.plan"],
        }
    )
    serialized = json.dumps(transitions) + json.dumps(loops) + json.dumps(backtracks)
    assert "dara@example.com" not in serialized
    assert "012345678" not in serialized
    assert "Dara" not in serialized


def test_workspace_conversion_does_not_complete_the_product_step() -> None:
    sequences = {
        f"s{index}": ["signup", "setup.company", "setup.plan", "dashboard", "products"]
        for index in range(MIN_SESSIONS)
    }
    sessions = {f"s{index}": {"user_id": f"u{index}", "company_id": None} for index in range(MIN_SESSIONS)}
    analysis = analyse_step_review(
        sequences=sequences,
        sessions=sessions,
        converted_users={f"u{index}" for index in range(MIN_SESSIONS)},
    )
    products = next(step for step in analysis["steps"] if step["key"] == "products")
    assert products["reached_sessions"] == MIN_SESSIONS
    # Creating a workspace completes the setup steps, never the product step.
    assert products["completed_sessions"] == 0


def test_marginal_conversion_formula_and_cap() -> None:
    # With the step: 2/2 convert. Without it: 0/2. Marginal = 1.0.
    assert marginal_conversion({"a", "b"}, {"a", "b", "c", "d"}, {"a", "b"}) == 1.0
    # With the step: 1/2. Without it: 1/2. Marginal = 0.0.
    assert marginal_conversion({"a", "b"}, {"a", "b", "c", "d"}, {"a", "c"}) == 0.0
    # With the step: 0/1. Without it: 1/1. Marginal = -1.0, and never below it.
    assert marginal_conversion({"a"}, {"a", "b"}, {"b"}) == -1.0
    # One side of the comparison missing is not zero, it is unknown.
    assert marginal_conversion({"a", "b"}, {"a", "b"}, {"a"}) is None
    assert marginal_conversion(set(), {"a", "b"}, {"a"}) is None


def test_sufficiency_threshold_blocks_the_analysis() -> None:
    thin = {f"s{i}": ["signup", "setup.company"] for i in range(MIN_SESSIONS - 1)}
    blocked = analyse_step_review(sequences=thin, sessions={}, window_days=30)
    assert blocked["insufficient"] is True
    assert blocked["steps"] == [] and blocked["evidence"] == []
    assert str(MIN_SESSIONS - 1) in blocked["reason"]
    assert str(MIN_SESSIONS) in blocked["reason"]

    enough = {f"s{i}": ["signup", "setup.company"] for i in range(MIN_SESSIONS)}
    ready = analyse_step_review(sequences=enough, sessions={}, window_days=30)
    assert ready["insufficient"] is False
    assert [step["key"] for step in ready["steps"]] == [
        "setup.company",
        "setup.questions",
        "setup.plan",
        "products",
    ]
    assert "step:setup.company:reached" in {item["id"] for item in ready["evidence"]}


def _analysis(*, count: int = 40, reached_company: int | None = None) -> dict:
    reached_company = count if reached_company is None else reached_company
    sequences = {}
    for index in range(count):
        if index < reached_company:
            sequences[f"s{index}"] = [
                "signup",
                "setup.company",
                "setup.questions",
                "setup.plan",
                "dashboard",
            ]
        else:
            sequences[f"s{index}"] = ["signup", "login"]
    events = {
        f"s{index}": [
            {
                "name": "page.left",
                "route_key": "setup.company",
                "duration_ms": 120_000,
                "properties": {"dwell_ms": 120_000},
            }
        ]
        for index in range(reached_company)
    }
    return analyse_step_review(
        sequences=sequences, sessions={}, events_by_session=events, window_days=30
    )


def _proposal(
    *,
    step_key: str = "setup.company",
    action: str = "remove",
    evidence: list[str] | None = None,
) -> dict:
    return {
        "step_key": step_key,
        "action": action,
        "rationale": "The step loops more than it converts.",
        "evidence": evidence or [],
        "risk": "Removing it may lose plan accuracy.",
        "estimated_effect": "Unknown until the experiment runs.",
        "confidence": 0.7,
        "experiment": {
            "hypothesis": "Removing the step does not reduce workspace creation.",
            "primary_metric": "verified_to_workspace",
            "guardrails": ["plan_mix"],
            "sample": "Sequential test over three weeks.",
            "judge_query": "GET /admin/journeys/funnel?cohort=signup&stage=workspace",
        },
    }


def _reply(proposal: dict, headline: str = "The setup flow loops") -> str:
    return json.dumps({"headline": headline, "proposals": [proposal]})


def test_validator_rejects_non_keep_without_step_evidence() -> None:
    analysis = _analysis(reached_company=20)
    reply = _reply(_proposal(action="remove", evidence=["trans:signup->setup.company"]))
    result = validate_step_review(reply, analysis)
    assert result.ok is False
    assert "cites no step:setup.company:" in (result.error or "")


def test_validator_rejects_remove_when_marginal_is_null() -> None:
    # Every session reached the step, so the "without the step" side is empty.
    analysis = _analysis(reached_company=40)
    step = next(row for row in analysis["steps"] if row["key"] == "setup.company")
    assert step["marginal_conversion"] is None
    reply = _reply(
        _proposal(
            action="remove",
            evidence=["step:setup.company:reached", "step:setup.company:back_rate"],
        )
    )
    result = validate_step_review(reply, analysis)
    assert result.ok is False
    assert "marginal_conversion is null" in (result.error or "")


def test_validator_accepts_a_cited_remove_when_marginal_exists() -> None:
    analysis = _analysis(reached_company=30)
    step = next(row for row in analysis["steps"] if row["key"] == "setup.company")
    assert step["marginal_conversion"] is not None
    reply = _reply(
        _proposal(
            action="remove",
            evidence=[
                "step:setup.company:reached",
                "step:setup.company:marginal",
                "step:setup.company:back_rate",
            ],
        )
    )
    result = validate_step_review(reply, analysis)
    assert result.ok is True, result.error


def test_validator_rejects_an_invented_step_or_evidence_id() -> None:
    analysis = _analysis(reached_company=30)
    invented_step = _reply(_proposal(step_key="setup.secret", action="keep", evidence=[]))
    assert validate_step_review(invented_step, analysis).ok is False

    unknown_id = _reply(
        _proposal(action="merge", evidence=["step:setup.company:invented_metric"])
    )
    result = validate_step_review(unknown_id, analysis)
    assert result.ok is False
    assert "not in the input" in (result.error or "")


def test_fallback_is_ranked_cited_and_never_removes() -> None:
    analysis = _analysis(reached_company=30)
    payload = fallback_step_review(analysis)
    assert 0 < len(payload["proposals"]) <= 3
    allowed = {item["id"] for item in analysis["evidence"]}
    for proposal in payload["proposals"]:
        assert proposal["action"] in {"keep", "merge"}
        assert any(item.startswith(f"step:{proposal['step_key']}:") for item in proposal["evidence"])
        assert set(proposal["evidence"]) <= allowed
        assert proposal["confidence"] == 0.4
    assert validate_step_review(json.dumps(payload), analysis).ok is True


# ---------------------------------------------------------------------------
# Endpoint helpers
# ---------------------------------------------------------------------------


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


async def _purge_reviews(days: int) -> None:
    async with SessionLocal() as db:
        await db.execute(
            text(
                "DELETE FROM activation_experiments WHERE insight_id IN "
                "(SELECT id FROM ai_insights WHERE kind = 'step_review' AND window_days = :days)"
            ),
            {"days": days},
        )
        await db.execute(
            text(
                "DELETE FROM ai_runs WHERE insight_id IN "
                "(SELECT id FROM ai_insights WHERE kind = 'step_review' AND window_days = :days)"
            ),
            {"days": days},
        )
        await db.execute(
            text("DELETE FROM ai_insights WHERE kind = 'step_review' AND window_days = :days"),
            {"days": days},
        )
        await db.commit()


async def _purge_sessions(session_ids: list[str]) -> None:
    async with SessionLocal() as db:
        for session_id in session_ids:
            await db.execute(
                text("DELETE FROM analytics_events WHERE session_id = :session_id"),
                {"session_id": session_id},
            )
            await db.execute(
                text("DELETE FROM analytics_sessions WHERE id = :session_id"),
                {"session_id": session_id},
            )
        await db.commit()


async def _seed_sessions(client: AsyncClient, count: int) -> list[str]:
    """Anonymous sessions that walk the three setup steps and quit at the dashboard."""
    session_ids: list[str] = []
    for index in range(count):
        session_id = str(uuid.uuid4())
        session_ids.append(session_id)
        events = [
            _event("page.viewed", {}, route_key="signup"),
            _event("page.viewed", {}, route_key="setup.company"),
            _event(
                "onboarding.step_viewed",
                {"step": 1, "step_key": "Company details"},
                route_key="setup.company",
            ),
            _event("page.left", {"dwell_ms": 4_000 + index * 100}, route_key="setup.company"),
            _event(
                "onboarding.step_completed",
                {"step": 1, "step_key": "Company details", "changed": index % 2 == 0},
                route_key="setup.company",
            ),
            _event("page.viewed", {}, route_key="setup.questions"),
            _event(
                "onboarding.step_completed",
                {"step": 2, "step_key": "A few quick questions", "changed": index % 3 == 0},
                route_key="setup.questions",
            ),
            _event("page.viewed", {}, route_key="setup.plan"),
            _event(
                "onboarding.step_back",
                {"from_step": 2, "to_step": 1},
                route_key="setup.questions",
            ),
            _event("page.viewed", {}, route_key="dashboard"),
        ]
        response = await client.post("/api/v1/telemetry/events", json=_batch(session_id, events))
        assert response.status_code == 202, response.text
    return session_ids


def _fake_reply(document: dict) -> str:
    step = next(
        (row for row in document["steps"] if int(row.get("reached_sessions") or 0) > 0),
        document["steps"][0],
    )
    ids = [
        item["id"]
        for item in document["evidence"]
        if item["id"].startswith(f"step:{step['key']}:")
    ]
    return json.dumps(
        {
            "headline": f"{step['label']} is the clearest step candidate",
            "proposals": [
                {
                    "step_key": step["key"],
                    "action": "keep",
                    "rationale": "Backtracking and dwell make this the strongest candidate, but the evidence does not justify removal.",
                    "evidence": ids[:3],
                    "risk": "Changing it may lose downstream conversion.",
                    "estimated_effect": "Unknown until the experiment runs.",
                    "confidence": 0.6,
                    "experiment": {
                        "hypothesis": "Merging this step does not reduce workspace creation.",
                        "primary_metric": "verified_to_workspace",
                        "guardrails": ["plan_mix", "support_tickets_per_100_workspaces"],
                        "sample": "Sequential test over three weeks.",
                        "judge_query": "GET /admin/journeys/funnel?cohort=signup&stage=workspace",
                    },
                }
            ],
        }
    )


def _patch_provider(monkeypatch: pytest.MonkeyPatch, calls: list[dict]) -> None:
    async def fake_complete_chat(db, *, system, messages, temperature=0.3, max_tokens=900):
        calls.append({"temperature": temperature, "max_tokens": max_tokens})
        document = json.loads(messages[0]["content"])
        return {
            "content": _fake_reply(document),
            "provider": "openai",
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 200, "completion_tokens": 90},
        }

    monkeypatch.setattr(step_review_ai, "complete_chat", fake_complete_chat)


async def _new_admin(client: AsyncClient, prefix: str) -> tuple[str, str, dict]:
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    workspace, _ = await create_free_workspace(client, email)
    await promote_to_admin(email)
    headers = await login_headers(client, email)
    return email, workspace["company"]["id"], headers


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


async def test_step_review_run_stores_cited_proposals_and_creates_a_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    days = 391
    admin_email = ""
    admin_company = None
    session_ids: list[str] = []
    calls: list[dict] = []
    try:
        await _set_ai_settings(True)
        await _purge_reviews(days)
        _patch_provider(monkeypatch, calls)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            session_ids = await _seed_sessions(client, MIN_SESSIONS + 6)
            admin_email, admin_company, admin_headers = await _new_admin(client, "step-review-ok")

            before = await client.get(
                "/api/v1/admin/journeys/step-review", headers=admin_headers, params={"days": days}
            )
            assert before.status_code == 200
            assert before.json() is None

            created = await client.post(
                "/api/v1/admin/journeys/step-review/run", headers=admin_headers, params={"days": days}
            )
            assert created.status_code == 200, created.text
            body = created.json()
            assert body["kind"] == "step_review"
            assert body["validator"] == "passed"
            assert body["provider"] == "openai"
            assert body["prompt_version"] == step_review_ai.PROMPT_VERSION
            assert body["decision"] is None
            allowed = {item["id"] for item in body["evidence"]}
            assert body["payload"]["proposals"]
            for proposal in body["payload"]["proposals"]:
                assert set(proposal["evidence"]) <= allowed
                assert proposal["action"] in {"merge", "remove", "reorder", "keep"}

            latest = await client.get(
                "/api/v1/admin/journeys/step-review", headers=admin_headers, params={"days": days}
            )
            assert latest.status_code == 200, latest.text
            assert latest.json()["id"] == body["id"]

            # A draft cannot be created before a human accepts.
            too_early = await client.post(
                "/api/v1/admin/journeys/experiments",
                headers=admin_headers,
                json={"insight_id": body["id"], "proposal_index": 0},
            )
            assert too_early.status_code == 400, too_early.text

            decided = await client.patch(
                f"/api/v1/admin/journeys/step-review/{body['id']}/decision",
                headers=admin_headers,
                json={"decision": "accepted", "note": "Matches the transition matrix."},
            )
            assert decided.status_code == 200, decided.text
            assert decided.json()["decision"] == "accepted"
            assert decided.json()["decision_note"] == "Matches the transition matrix."

            experiment = await client.post(
                "/api/v1/admin/journeys/experiments",
                headers=admin_headers,
                json={"insight_id": body["id"], "proposal_index": 0},
            )
            assert experiment.status_code == 201, experiment.text
            draft = experiment.json()
            assert draft["status"] == "draft"
            assert draft["insight_id"] == body["id"]
            assert draft["stage_key"] == body["payload"]["proposals"][0]["step_key"]
            assert draft["variant"]["proposal_index"] == 0
            assert draft["variant"]["action"] == "keep"

            duplicate = await client.post(
                "/api/v1/admin/journeys/experiments",
                headers=admin_headers,
                json={"insight_id": body["id"], "proposal_index": 0},
            )
            assert duplicate.status_code == 409

            listed = await client.get("/api/v1/admin/journeys/experiments", headers=admin_headers)
            assert listed.status_code == 200
            assert any(row["id"] == draft["id"] and row["status"] == "draft" for row in listed.json())

        async with SessionLocal() as db:
            insight = await db.get(AIInsight, uuid.UUID(body["id"]))
            assert insight is not None and insight.kind == "step_review"
            runs = (
                await db.execute(select(AIRun).where(AIRun.insight_id == insight.id))
            ).scalars().all()
            assert [run.outcome for run in runs] == ["ok"]
            stored = (
                await db.execute(
                    select(ActivationExperiment).where(
                        ActivationExperiment.insight_id == insight.id
                    )
                )
            ).scalars().all()
            assert len(stored) == 1 and stored[0].status == "draft"
        assert len(calls) == 1
        assert calls[0]["temperature"] == 0.2
        assert calls[0]["max_tokens"] == 900
    finally:
        await _set_ai_settings(False)
        await _purge_reviews(days)
        await _purge_sessions(session_ids)
        if admin_email:
            await cleanup(admin_email, admin_company)


async def test_step_review_falls_back_after_two_invalid_replies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    days = 392
    admin_email = ""
    admin_company = None
    session_ids: list[str] = []
    calls: list[int] = []
    try:
        await _set_ai_settings(True)
        await _purge_reviews(days)

        async def garbage(db, *, system, messages, temperature=0.3, max_tokens=900):
            calls.append(1)
            return {
                "content": "not json",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            }

        monkeypatch.setattr(step_review_ai, "complete_chat", garbage)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            session_ids = await _seed_sessions(client, MIN_SESSIONS + 2)
            admin_email, admin_company, admin_headers = await _new_admin(client, "step-review-fallback")
            created = await client.post(
                "/api/v1/admin/journeys/step-review/run", headers=admin_headers, params={"days": days}
            )
            assert created.status_code == 200, created.text
            body = created.json()

        assert len(calls) == 2, "one repair attempt, then deterministic fallback"
        assert body["validator"] == "fallback"
        assert body["payload"]["proposals"]
        allowed = {item["id"] for item in body["evidence"]}
        for proposal in body["payload"]["proposals"]:
            assert proposal["action"] in {"keep", "merge"}
            assert any(item.startswith(f"step:{proposal['step_key']}:") for item in proposal["evidence"])
            assert set(proposal["evidence"]) <= allowed
        async with SessionLocal() as db:
            runs = (
                await db.execute(select(AIRun).where(AIRun.insight_id == uuid.UUID(body["id"])))
            ).scalars().all()
            assert [run.outcome for run in runs] == ["parse_error", "parse_error"]
    finally:
        await _set_ai_settings(False)
        await _purge_reviews(days)
        await _purge_sessions(session_ids)
        if admin_email:
            await cleanup(admin_email, admin_company)


async def test_step_review_returns_400_when_ai_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    days = 393
    admin_email = ""
    admin_company = None
    try:
        await _set_ai_settings(False)

        async def prepared(db, *, days=30):
            return _analysis(reached_company=30)

        async def must_not_run(db, *, system, messages, temperature=0.3, max_tokens=900):
            raise AssertionError("the provider must not be called without configuration")

        monkeypatch.setattr(step_review_ai, "build_step_review", prepared)
        monkeypatch.setattr(step_review_ai, "complete_chat", must_not_run)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_email, admin_company, admin_headers = await _new_admin(client, "step-review-noconfig")
            response = await client.post(
                "/api/v1/admin/journeys/step-review/run", headers=admin_headers, params={"days": days}
            )
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "Configure AI in Settings > AI writing"
    finally:
        await _set_ai_settings(False)
        await _purge_reviews(days)
        if admin_email:
            await cleanup(admin_email, admin_company)


async def test_step_review_returns_503_when_the_kill_switch_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    days = 394
    admin_email = ""
    admin_company = None
    try:
        await _set_ai_settings(True)
        monkeypatch.setattr(step_review_ai.settings, "activation_ai_enabled", False)

        async def must_not_run(db, *, system, messages, temperature=0.3, max_tokens=900):
            raise AssertionError("the provider must not be called while disabled")

        monkeypatch.setattr(step_review_ai, "complete_chat", must_not_run)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_email, admin_company, admin_headers = await _new_admin(client, "step-review-off")
            response = await client.post(
                "/api/v1/admin/journeys/step-review/run", headers=admin_headers, params={"days": days}
            )
        assert response.status_code == 503, response.text
        assert "disabled" in response.json()["detail"].lower()
    finally:
        await _set_ai_settings(False)
        if admin_email:
            await cleanup(admin_email, admin_company)


async def test_step_review_is_insufficient_below_thirty_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    days = 395
    admin_email = ""
    admin_company = None
    try:
        await _set_ai_settings(True)
        await _purge_reviews(days)

        async def thin(db, *, days=30):
            return {
                "window_days": days,
                "insufficient": True,
                "reason": "Only 5 sessions in this window; at least 30 are needed for a step review.",
                "sessions": 5,
                "transitions": [],
                "loops": [],
                "backtracks": [],
                "steps": [],
                "survey": [],
                "evidence": [],
            }

        async def must_not_run(db, *, system, messages, temperature=0.3, max_tokens=900):
            raise AssertionError("an insufficient window must not reach a provider")

        monkeypatch.setattr(step_review_ai, "build_step_review", thin)
        monkeypatch.setattr(step_review_ai, "complete_chat", must_not_run)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_email, admin_company, admin_headers = await _new_admin(client, "step-review-thin")
            created = await client.post(
                "/api/v1/admin/journeys/step-review/run", headers=admin_headers, params={"days": days}
            )
            assert created.status_code == 200, created.text
            body = created.json()

        assert body["validator"] == "insufficient"
        assert body["payload"]["insufficient"] is True
        assert "30" in body["payload"]["reason"]
        assert body["payload"]["proposals"] == []
        assert body["provider"] is None and body["model"] is None
        async with SessionLocal() as db:
            runs = (
                await db.execute(select(AIRun).where(AIRun.insight_id == uuid.UUID(body["id"])))
            ).scalars().all()
            assert runs == []
    finally:
        await _set_ai_settings(False)
        await _purge_reviews(days)
        if admin_email:
            await cleanup(admin_email, admin_company)


async def test_step_review_endpoints_are_platform_admin_only() -> None:
    email = f"step-review-denied-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace, headers = await create_free_workspace(client, email)
            company_id = workspace["company"]["id"]
            denied_run = await client.post("/api/v1/admin/journeys/step-review/run", headers=headers)
            denied_read = await client.get("/api/v1/admin/journeys/step-review", headers=headers)
            denied_decision = await client.patch(
                f"/api/v1/admin/journeys/step-review/{uuid.uuid4()}/decision",
                headers=headers,
                json={"decision": "accepted"},
            )
            denied_create = await client.post(
                "/api/v1/admin/journeys/experiments",
                headers=headers,
                json={"insight_id": str(uuid.uuid4()), "proposal_index": 0},
            )
            denied_list = await client.get("/api/v1/admin/journeys/experiments", headers=headers)
        assert denied_run.status_code == 403
        assert denied_read.status_code == 403
        assert denied_decision.status_code == 403
        assert denied_create.status_code == 403
        assert denied_list.status_code == 403
    finally:
        await cleanup(email, company_id)
