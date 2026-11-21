"""The AI half of the step review: one narrative, cited, never applied.

The deterministic part lives in :mod:`app.services.step_review`. This module
takes its document unchanged, asks one configured model for at most five
proposals plus a headline, validates every step key and evidence id against that
document, and stores the result as an ``ai_insights`` row of kind
``step_review``. When the provider fails or returns an unsupported reply, a
deterministic rules ranking is stored instead and labelled ``fallback``.

Nothing here changes a flow, a flag, copy or traffic. An accepted proposal can
create a draft :class:`~app.models.ActivationExperiment`; enabling it remains a
separate human action outside this feature.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AIInsight, AIRun, ActivationExperiment
from app.services.activation_ai import (
    ActivationAIDisabled,
    ValidationResult,
    _hash,
    _parse_json,
    _unsupported_number,
)
from app.services.ai import (
    AINotConfiguredError,
    AIError,
    complete_chat,
    load_ai_settings,
    require_chat_config,
    resolve_provider,
)
from app.services.ai_pricing import estimate_cost_usd, load_prices
from app.services.step_review import build_step_review
from app.services.support import record_usage

KIND = "step_review"
PROMPT_VERSION = "step_review_v1"
TEMPERATURE = 0.2
MAX_TOKENS = 900
MAX_PROPOSALS = 5
MAX_HEADLINE_CHARS = 300
MAX_TEXT_CHARS = 600
MAX_SHORT_CHARS = 300
ACTIONS = ("merge", "remove", "reorder", "keep")

SYSTEM_PROMPT = """\
You are the activation step reviewer for Chmaba, a cloud point-of-sale platform \
for retail shops in Cambodia. You receive one JSON document computed by \
deterministic SQL over route transitions and step events. Your job is to explain \
which steps to merge, remove, reorder or keep, and to design the experiment that \
would prove it.

Hard rules:
1. Reply with strict JSON only. No markdown, no code fences, no commentary.
2. Use only the step keys listed under "steps". Never invent a step, route or \
stage.
3. Every evidence id you cite MUST appear in the "evidence" list. Copy ids \
exactly.
4. Any proposal whose action is not "keep" MUST cite at least one evidence id of \
the form "step:<step_key>:<metric>" for its own step.
5. Never propose "remove" for a step whose "marginal_conversion" is null. Without \
that comparison you cannot show removal preserves downstream conversion; propose \
"merge", "reorder" or "keep" instead.
6. Do not state a number that is not in the cited evidence. Prefer naming the \
evidence id over paraphrasing a figure.
7. Do not mention names, emails, phone numbers, user or company ids, URLs or \
free text. Only aggregate counts, ratios and registry keys exist here.
8. Return at most five proposals. Order them by expected value, strongest first.
9. This is advice for a human. Nothing is applied automatically, so make the risk \
and the experiment explicit.

Required output shape:
{"headline": "one sentence", "proposals": [{"step_key": "step_key", "action": \
"merge|remove|reorder|keep", "rationale": "one or two sentences", "evidence": \
["evidence id"], "risk": "one sentence", "estimated_effect": "one sentence", \
"confidence": 0.0, "experiment": {"hypothesis": "one sentence", "primary_metric": \
"metric key", "guardrails": ["metric key"], "sample": "how much traffic or time", \
"judge_query": "the exact admin query that will judge it"}}]}"""

REPAIR_PROMPT = """\
Your previous reply was rejected by the validator: {error}
Reply again with strict JSON only. Use only step keys and evidence ids from the \
document, cite step:<step_key>:<metric> for any non-keep action, and never propose \
remove when marginal_conversion is null. No markdown, no prose."""


class StepReviewNotAccepted(ValueError):
    """The insight exists but a human has not accepted it yet."""


class StepReviewProposalMissing(ValueError):
    """The requested proposal index does not exist on the insight."""


class StepReviewExperimentExists(ValueError):
    """An experiment draft already exists for this insight and proposal."""


# "p90" is a metric name, not a figure. Strip percentile labels before the
# lexical number check so a correct sentence is not rejected for saying "p90".
_PERCENTILE_TOKEN = re.compile(r"\bp(?:50|90|95|99)\b", re.IGNORECASE)


def _unsupported_claim_number(
    claim: str, cited: list[str], by_id: dict[str, dict[str, Any]]
) -> str | None:
    cleaned = _PERCENTILE_TOKEN.sub("percentile", claim)
    return _unsupported_number(cleaned, cited, by_id)


def prompt_document(analysis: dict[str, Any]) -> dict[str, Any]:
    """The provider payload: aggregate counts, keys and the allowed id set."""
    return {
        "prompt_version": PROMPT_VERSION,
        "window": {"days": int(analysis.get("window_days") or 0)},
        "sessions": int(analysis.get("sessions") or 0),
        "transitions": analysis.get("transitions") or [],
        "loops": analysis.get("loops") or [],
        "backtracks": analysis.get("backtracks") or [],
        "steps": analysis.get("steps") or [],
        "survey": analysis.get("survey") or [],
        "evidence": [
            {"id": item["id"], "value": item["value"], "unit": item["unit"]}
            for item in analysis.get("evidence") or []
        ],
    }


def _text(value: Any, *, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > limit:
        return None
    return cleaned


def validate_step_review(raw: str, analysis: dict[str, Any]) -> ValidationResult:
    """Validate a model reply against the deterministic document.

    Rejected: non-JSON, a missing headline, more than five proposals, an unknown
    step key or action, an id that is not in the deterministic set, an uncited
    proposal, a non-keep proposal that cites no ``step:<key>:*`` evidence, and a
    ``remove`` proposal for a step whose marginal conversion is null. Numbers in
    the rationale and estimated effect must resolve to a cited evidence value.
    """
    payload = _parse_json(raw)
    if payload is None:
        return ValidationResult(None, "Reply is not a JSON object.")

    by_id = {str(item["id"]): item for item in analysis.get("evidence") or []}
    steps = {str(step["key"]): step for step in analysis.get("steps") or []}

    headline = _text(payload.get("headline"), limit=MAX_HEADLINE_CHARS)
    if headline is None:
        return ValidationResult(None, f"headline must be a non-empty string under {MAX_HEADLINE_CHARS} characters.")

    proposals = payload.get("proposals")
    if not isinstance(proposals, list):
        return ValidationResult(None, "proposals must be a list.")
    if len(proposals) > MAX_PROPOSALS:
        return ValidationResult(None, f"proposals must contain at most {MAX_PROPOSALS} items.")

    for index, proposal in enumerate(proposals):
        label = f"proposals[{index}]"
        if not isinstance(proposal, dict):
            return ValidationResult(None, f"{label} must be an object.")
        step_key = proposal.get("step_key")
        if not isinstance(step_key, str) or step_key not in steps:
            return ValidationResult(None, f"{label}.step_key is not a step in the deterministic analysis.")
        action = proposal.get("action")
        if action not in ACTIONS:
            return ValidationResult(
                None, f"{label}.action must be one of {', '.join(ACTIONS)}."
            )
        rationale = _text(proposal.get("rationale"), limit=MAX_TEXT_CHARS)
        if rationale is None:
            return ValidationResult(None, f"{label}.rationale must be a non-empty string.")
        cited = proposal.get("evidence")
        if not isinstance(cited, list) or not cited:
            return ValidationResult(None, f"{label} cites no evidence.")
        if any(not isinstance(item, str) for item in cited):
            return ValidationResult(None, f"{label}.evidence must be a list of ids.")
        unknown = [item for item in cited if item not in by_id]
        if unknown:
            return ValidationResult(
                None, f"{label} cites an evidence id that is not in the input: {unknown[0]}"
            )
        if action != "keep" and not any(
            item.startswith(f"step:{step_key}:") for item in cited
        ):
            return ValidationResult(
                None,
                f"{label} uses action '{action}' but cites no step:{step_key}:* evidence.",
            )
        if action == "remove" and steps[step_key].get("marginal_conversion") is None:
            return ValidationResult(
                None,
                f"{label} proposes remove for a step whose marginal_conversion is null.",
            )
        for field in ("risk", "estimated_effect"):
            if _text(proposal.get(field), limit=MAX_SHORT_CHARS) is None:
                return ValidationResult(None, f"{label}.{field} must be a non-empty string.")
        unsupported = _unsupported_claim_number(rationale, cited, by_id)
        if unsupported is not None:
            return ValidationResult(
                None, f"{label}.rationale uses a number that is not in the cited evidence: {unsupported}"
            )
        unsupported = _unsupported_claim_number(str(proposal.get("estimated_effect") or ""), cited, by_id)
        if unsupported is not None:
            return ValidationResult(
                None,
                f"{label}.estimated_effect uses a number that is not in the cited evidence: {unsupported}",
            )

        experiment = proposal.get("experiment")
        if not isinstance(experiment, dict):
            return ValidationResult(None, f"{label}.experiment must be an object.")
        for field in ("hypothesis", "primary_metric", "sample", "judge_query"):
            if _text(experiment.get(field), limit=MAX_TEXT_CHARS) is None:
                return ValidationResult(None, f"{label}.experiment.{field} must be a non-empty string.")
        guardrails = experiment.get("guardrails")
        if not isinstance(guardrails, list) or not guardrails:
            return ValidationResult(None, f"{label}.experiment.guardrails must be a non-empty list.")
        if any(not isinstance(item, str) or not item.strip() for item in guardrails):
            return ValidationResult(None, f"{label}.experiment.guardrails must contain metric keys.")
        confidence = proposal.get("confidence", 0.5)
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            return ValidationResult(None, f"{label}.confidence must be a number.")
        if not 0.0 <= float(confidence) <= 1.0:
            return ValidationResult(None, f"{label}.confidence must be between 0 and 1.")
        proposal["confidence"] = round(float(confidence), 2)

    return ValidationResult({"headline": headline, "proposals": proposals})


def _step_score(step: dict[str, Any]) -> float:
    """Deterministic ranking: back rate + normalised p90 + downside of the step.

    The p90 is normalised against 15 minutes, matching the friction score's
    order of magnitude, so a 3-second screen never outranks a looping one. The
    marginal term only contributes when it is negative: a step that is
    associated with *more* downstream conversion is not a reduction candidate.
    """
    back_rate = float(step.get("back_rate") or 0.0)
    p90 = float(step.get("p90_dwell_ms") or 0.0)
    dwell = min(p90 / 900_000.0, 1.0)
    marginal = step.get("marginal_conversion")
    downside = max(0.0, -float(marginal)) if marginal is not None else 0.0
    return round(back_rate + dwell + downside, 4)


def _step_evidence(step: dict[str, Any]) -> list[str]:
    ids = [f"step:{step['key']}:reached"]
    if step.get("p90_dwell_ms") is not None:
        ids.append(f"step:{step['key']}:dwell_p90")
    if step.get("back_rate") is not None:
        ids.append(f"step:{step['key']}:back_rate")
    if step.get("marginal_conversion") is not None:
        ids.append(f"step:{step['key']}:marginal")
    return ids


def fallback_step_review(analysis: dict[str, Any]) -> dict[str, Any]:
    """Deterministic rules answer, labelled ``fallback``.

    Ranks the three strongest observed steps by the same score the UI explains,
    keeps only ``keep``/``merge``, and never puts a number into prose that is not
    in the evidence. Confidence is fixed at 0.4 because rules rank, they do not
    interpret.
    """
    steps = [step for step in analysis.get("steps") or [] if int(step.get("reached_sessions") or 0) > 0]
    ranked = sorted(steps, key=lambda step: (-_step_score(step), step["key"]))[:3]
    proposals: list[dict[str, Any]] = []
    for step in ranked:
        label = step.get("label") or step["key"]
        marginal = step.get("marginal_conversion")
        action = "merge" if marginal is not None and float(marginal) < 0 else "keep"
        if action == "merge":
            rationale = (
                f"{label} has the strongest combination of backtracking, p90 dwell and negative "
                "marginal conversion among the tracked steps. Treat it as a merge candidate, not a "
                "removal: the marginal value is an association, not proof that the step is safe to delete."
            )
            hypothesis = f"Merging {label} into the next step does not reduce workspace creation."
            risk = "Merging may change the plan recommendation for multi-store merchants."
        else:
            rationale = (
                f"{label} is ranked by backtracking, p90 dwell and marginal conversion, but the "
                "evidence does not justify removing or merging it without a test."
            )
            hypothesis = f"Keeping {label} unchanged does not lose more sessions than a merged variant."
            risk = "Changing a step that already converts risks losing its downstream conversion."
        proposals.append(
            {
                "step_key": step["key"],
                "action": action,
                "rationale": rationale,
                "evidence": _step_evidence(step),
                "risk": risk,
                "estimated_effect": "Unknown until the experiment runs.",
                "confidence": 0.4,
                "experiment": {
                    "hypothesis": hypothesis,
                    "primary_metric": "verified_to_workspace",
                    "guardrails": ["plan_mix", "support_tickets_per_100_workspaces"],
                    "sample": "Sequential before/after test over at least three weeks, or until each arm has enough sessions to judge the primary metric.",
                    "judge_query": "GET /admin/journeys/funnel?cohort=signup&stage=workspace",
                },
            }
        )
    if proposals:
        headline = f"{ranked[0].get('label') or ranked[0]['key']} is the strongest step candidate in this window"
    else:
        headline = "No tracked step was reached in this window"
    return {"headline": headline, "proposals": proposals}


def _severity(analysis: dict[str, Any]) -> str:
    for step in analysis.get("steps") or []:
        if not step.get("reached_sessions"):
            continue
        if float(step.get("back_rate") or 0.0) >= 0.2:
            return "medium"
        marginal = step.get("marginal_conversion")
        if marginal is not None and float(marginal) <= -0.1:
            return "medium"
        if float(step.get("p90_dwell_ms") or 0.0) >= 600_000:
            return "medium"
    return "low"


def _summary(payload: dict[str, Any], analysis: dict[str, Any]) -> str:
    if payload.get("insufficient"):
        return str(payload.get("reason") or "Not enough evidence yet.")
    proposals = payload.get("proposals") or []
    if not proposals:
        return "No tracked step was reached in this window."
    return (
        f"{len(proposals)} step proposal{'s' if len(proposals) != 1 else ''} "
        f"ranked from {int(analysis.get('sessions') or 0)} sessions."
    )


def _insight_row(
    analysis: dict[str, Any],
    payload: dict[str, Any],
    *,
    validator: str,
    provider: str | None,
    model: str | None,
) -> AIInsight:
    proposals = payload.get("proposals") or []
    scores = [
        float(proposal["confidence"])
        for proposal in proposals
        if isinstance(proposal.get("confidence"), (int, float))
    ]
    first_step = proposals[0]["step_key"] if proposals else None
    return AIInsight(
        kind=KIND,
        window_days=int(analysis.get("window_days") or 0),
        stage_key=first_step,
        title=str(payload.get("headline") or "Activation step review")[:MAX_HEADLINE_CHARS],
        summary=_summary(payload, analysis),
        severity=_severity(analysis) if validator != "insufficient" else "low",
        confidence=round(sum(scores) / len(scores), 2) if scores else None,
        evidence=analysis.get("evidence") or [],
        payload=payload,
        prompt_version=PROMPT_VERSION,
        provider=provider,
        model=model,
        input_hash=_hash(prompt_document(analysis)),
        validator=validator,
    )


async def generate_step_review(db: AsyncSession, *, days: int = 30) -> AIInsight:
    """Generate, validate and store one step review for the window.

    Raises :class:`ActivationAIDisabled` when the kill switch is off and
    ``AINotConfiguredError`` when no provider exists. A provider failure is a
    200 with a rules-based review, because the deterministic ranking is still
    useful. An insufficient window returns before the configuration check, so a
    quiet install never needs an API key.
    """
    if not settings.activation_ai_enabled:
        raise ActivationAIDisabled(
            "AI step review generation is disabled (ACTIVATION_AI_ENABLED=false)."
        )

    analysis = await build_step_review(db, days=days)
    if analysis["insufficient"]:
        payload = {
            "headline": "Not enough evidence yet",
            "proposals": [],
            "insufficient": True,
            "reason": analysis.get("reason") or "Not enough evidence yet.",
        }
        insight = _insight_row(
            analysis, payload, validator="insufficient", provider=None, model=None
        )
        db.add(insight)
        await db.commit()
        await db.refresh(insight)
        return insight

    await require_chat_config(db)
    configured = await load_ai_settings(db)
    provider_config, model_name = resolve_provider(configured)
    provider = provider_config.code if provider_config else None

    runs: list[dict[str, Any]] = []
    payload: dict[str, Any] | None = None
    validator = "passed"
    messages: list[dict[str, str]] = [
        {
            "role": "user",
            "content": json.dumps(
                prompt_document(analysis), sort_keys=True, separators=(",", ":")
            ),
        }
    ]

    async def attempt(conversation: list[dict[str, str]]) -> str:
        started = time.monotonic()
        try:
            result = await complete_chat(
                db,
                system=SYSTEM_PROMPT,
                messages=conversation,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
        except Exception:
            runs.append(
                {
                    "provider": provider,
                    "model": model_name,
                    "usage": {},
                    "latency_ms": int((time.monotonic() - started) * 1000),
                    "outcome": "provider_error",
                }
            )
            raise
        usage = result.get("usage") or {}
        runs.append(
            {
                "provider": result.get("provider") or provider,
                "model": result.get("model") or model_name,
                "usage": usage,
                "latency_ms": int((time.monotonic() - started) * 1000),
                "outcome": "ok",
            }
        )
        return str(result.get("content") or "")

    try:
        raw = await attempt(messages)
        outcome = validate_step_review(raw, analysis)
        if outcome.ok:
            payload = outcome.payload
        else:
            runs[-1]["outcome"] = "parse_error"
            repair = [
                *messages,
                {"role": "assistant", "content": raw[:6000]},
                {
                    "role": "user",
                    "content": REPAIR_PROMPT.format(error=outcome.error or "invalid JSON"),
                },
            ]
            repaired_raw = await attempt(repair)
            repaired = validate_step_review(repaired_raw, analysis)
            if repaired.ok:
                payload, validator = repaired.payload, "repaired"
            else:
                runs[-1]["outcome"] = "parse_error"
                payload, validator = fallback_step_review(analysis), "fallback"
    except AINotConfiguredError:
        raise
    except AIError:
        payload, validator = fallback_step_review(analysis), "fallback"

    if payload is None:  # defensive; the branches above always set it
        payload, validator = fallback_step_review(analysis), "fallback"

    insight = _insight_row(
        analysis, payload, validator=validator, provider=provider, model=model_name
    )
    db.add(insight)
    await db.flush()

    prices = await load_prices(db)
    for run in runs:
        usage = run.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        model_used = run.get("model") or model_name
        db.add(
            AIRun(
                insight_id=insight.id,
                prompt_version=PROMPT_VERSION,
                provider=run.get("provider"),
                model=model_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=round(
                    estimate_cost_usd(model_used, prompt_tokens, completion_tokens, prices), 6
                ),
                latency_ms=int(run.get("latency_ms") or 0),
                outcome=run.get("outcome") or "ok",
            )
        )
    await db.commit()
    await db.refresh(insight)

    for run in runs:
        usage = dict(run.get("usage") or {})
        usage["provider"] = run.get("provider") or provider or "unknown"
        usage["model"] = run.get("model") or model_name or "unknown"
        await record_usage(usage=usage, company_id=None)
    return insight


async def latest_step_review(db: AsyncSession, *, days: int = 30) -> AIInsight | None:
    """The most recent step review for one window, or ``None``."""
    return await db.scalar(
        select(AIInsight)
        .where(AIInsight.kind == KIND, AIInsight.window_days == int(days))
        .order_by(AIInsight.created_at.desc())
        .limit(1)
    )


async def decide_step_review(
    db: AsyncSession,
    *,
    insight_id: UUID,
    decision: str,
    note: str | None,
    decided_by: UUID,
) -> AIInsight | None:
    """Store a human accept/reject. No product change follows from it."""
    insight = await db.get(AIInsight, insight_id)
    if insight is None or insight.kind != KIND:
        return None
    insight.decision = decision
    insight.decided_by = decided_by
    insight.decided_at = datetime.now(timezone.utc)
    insight.decision_note = (note or "").strip() or None
    await db.commit()
    await db.refresh(insight)
    return insight


async def list_draft_experiments(db: AsyncSession, *, limit: int = 50) -> list[ActivationExperiment]:
    """Draft experiments only: this feature never runs or ships anything."""
    rows = await db.execute(
        select(ActivationExperiment)
        .where(ActivationExperiment.status == "draft")
        .order_by(ActivationExperiment.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars().all())


async def create_experiment_from_proposal(
    db: AsyncSession,
    *,
    insight_id: UUID,
    proposal_index: int,
) -> ActivationExperiment:
    """Create a draft experiment from an accepted proposal.

    The row is always ``status='draft'``: there is no traffic split, no flag and
    no copy change. Duplicate creation for the same insight/proposal is refused
    so a double click cannot create two records for one decision.
    """
    insight = await db.get(AIInsight, insight_id)
    if insight is None or insight.kind != KIND:
        raise StepReviewProposalMissing("Step review not found.")
    if insight.decision != "accepted":
        raise StepReviewNotAccepted("Accept the step review before creating an experiment draft.")
    proposals = (insight.payload or {}).get("proposals") or []
    if proposal_index < 0 or proposal_index >= len(proposals):
        raise StepReviewProposalMissing("Proposal index is out of range.")
    existing = await db.execute(
        select(ActivationExperiment).where(ActivationExperiment.insight_id == insight_id)
    )
    for experiment in existing.scalars().all():
        if int((experiment.variant or {}).get("proposal_index", -1)) == proposal_index:
            raise StepReviewExperimentExists("An experiment draft already exists for this proposal.")

    proposal = proposals[proposal_index]
    experiment_spec = proposal.get("experiment") or {}
    experiment = ActivationExperiment(
        hypothesis=str(experiment_spec.get("hypothesis") or "").strip(),
        stage_key=str(proposal.get("step_key") or "").strip(),
        primary_metric=str(experiment_spec.get("primary_metric") or "").strip(),
        guardrails=[str(item) for item in experiment_spec.get("guardrails") or []],
        variant={
            "proposal_index": proposal_index,
            "action": proposal.get("action"),
            "rationale": proposal.get("rationale"),
            "risk": proposal.get("risk"),
            "estimated_effect": proposal.get("estimated_effect"),
            "evidence": proposal.get("evidence") or [],
            "sample": experiment_spec.get("sample"),
            "judge_query": experiment_spec.get("judge_query"),
        },
        status="draft",
        insight_id=insight.id,
    )
    db.add(experiment)
    await db.commit()
    await db.refresh(experiment)
    return experiment
