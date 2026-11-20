"""Cited, human-reviewed friction digest for the activation funnel.

The division of labour is deliberate and is the whole design:

- :mod:`app.services.activation` computes *where* the cohort leaks.
- :mod:`app.services.journey_diagnostics` computes *why* a stage leaks
  (validation failures, failed requests, dead/rage clicks, dwell, survey).
- This module turns those deterministic numbers into a small evidence document,
  asks one configured model to rank and explain it, and validates the reply
  against the evidence before anything is stored.
- If the model is unavailable or produces an unsupported answer, a deterministic
  rules digest is stored instead and labelled ``validator='fallback'``.

Privacy is enforced by construction, not by asking the model nicely. The
evidence document contains only aggregate counts, ratios, milliseconds, and
registry-owned codes (stage keys, route-independent endpoint keys, element keys,
fixed survey codes). It never contains a user/company id, a name, an email, a
phone, a URL, a free-text survey answer, or arbitrary event properties. Keys
that do not look like code identifiers are dropped rather than passed through,
so a client that smuggles free text into ``element_key`` cannot reach a provider.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AIInsight, AIRun
from app.services.activation import build_funnel
from app.services.ai import (
    AINotConfiguredError,
    AIError,
    complete_chat,
    load_ai_settings,
    require_chat_config,
    resolve_provider,
)
from app.services.ai_pricing import estimate_cost_usd, load_prices
from app.services.journey_diagnostics import STAGE_ROUTES, build_stage_why
from app.services.support import record_usage

PROMPT_VERSION = "activation_digest_v1"
KIND = "digest"
TOP_STAGES = 5
MIN_EVENTS = 20
TEMPERATURE = 0.2
MAX_TOKENS = 900
REPAIR_ATTEMPTS = 1
MAX_TITLE_CHARS = 300
MAX_CLAIM_CHARS = 600

# Fixed codes from apps/web/src/lib/abandonSurvey.js. Anything else (including
# the "Other" free text) is counted under ``other`` and never reproduced.
SURVEY_CODES = frozenset({"thinking", "unclear", "broken", "expensive"})
SURVEY_OTHER = "other"

SEVERITIES = ("low", "medium", "high")
_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}

# A registry key is lowercase ASCII with dots/dashes/underscores. This is
# stricter than "printable", on purpose: prose, names, phone numbers and email
# addresses do not match, so they are dropped before they can become evidence.
_SAFE_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

SYSTEM_PROMPT = """\
You are the activation analyst for Chmaba, a cloud point-of-sale platform for \
retail shops in Cambodia. You receive one JSON evidence document produced by \
deterministic SQL queries. Your job is to rank the friction and explain it.

Hard rules:
1. Reply with strict JSON only. No markdown, no code fences, no commentary.
2. Every finding MUST cite at least one evidence id that appears in the input.
   Copy ids exactly; never invent an id or a stage.
3. Use only the stage keys listed under "stages".
4. Copy numbers exactly as they appear in the input, with the same unit. Never \
compute a percentage, average or total that is not already an evidence value.
5. Do not mention names, emails, phone numbers, user or company ids, URLs, or \
free-text survey answers. Only aggregate counts and registry keys exist here.
6. severity is one of "low", "medium", "high". confidence is a number from 0 \
to 1. Prefer lower confidence when the sample is small.
7. If no stage shows material friction, return an empty findings list, an empty \
recommended_focus (""), and insufficient_evidence false. Do not invent a problem.

Required output shape:
{"headline": "one sentence", "findings": [{"stage": "stage_key", "severity": \
"low|medium|high", "claim": "one or two sentences", "evidence": ["evidence id"], \
"confidence": 0.0}], "recommended_focus": "stage_key or empty string", \
"insufficient_evidence": false}"""

REPAIR_PROMPT = """\
Your previous reply was rejected by the validator: {error}
Reply again with strict JSON only. Use only stage keys and evidence ids from the \
evidence document, and copy numbers exactly. No markdown, no prose."""


class ActivationAIDisabled(RuntimeError):
    """The platform kill switch is off; generation must not run."""


@dataclass(frozen=True)
class ValidationResult:
    payload: dict[str, Any] | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.payload is not None


def _hash(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "input_hash"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_key(value: Any) -> str | None:
    """A registry-owned code, or ``None``. Never returns free text."""
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    if not cleaned or len(cleaned) > 80:
        return None
    return cleaned if _SAFE_KEY.match(cleaned) else None


def _count(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


class _Collector:
    """Accumulates the flat evidence list and the inline id/value pairs."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(
        self,
        evidence_id: str,
        *,
        stage: str | None,
        metric: str,
        value: Any,
        unit: str,
        context: list[Any] | None = None,
    ) -> dict[str, Any]:
        item: dict[str, Any] = {
            "id": evidence_id,
            "stage": stage,
            "metric": metric,
            "value": value,
            "unit": unit,
        }
        if context:
            item["context"] = context
        self.items.append(item)
        return {"id": evidence_id, "value": value}


def _rank_stages(funnel: dict[str, Any], *, limit: int = TOP_STAGES) -> list[dict[str, Any]]:
    """Top stages by a deterministic friction score, not by model opinion.

    The weights mirror the intent of A4.3 but only use numbers this service
    already has: how much of the previous stage continued, how long p90 takes,
    and how much of the cohort stalled. Kept in code so a score can never be
    attributed to the model.
    """
    total = _count(funnel.get("total"))
    ranked: list[dict[str, Any]] = []
    for index, stage in enumerate(funnel.get("stages") or []):
        key = str(stage.get("key") or "")
        if key not in STAGE_ROUTES:
            # ``second_sale`` has no diagnostic routes, so it cannot be explained.
            continue
        previous = stage.get("from_previous")
        abandon = 0.0
        if previous is not None:
            abandon = max(0.0, min(1.0, 1.0 - float(previous)))
        p90 = float(stage.get("p90_seconds") or 0.0)
        dwell = max(0.0, min(p90 / 900.0, 1.0))
        stalled = _count(stage.get("stalled"))
        stall_rate = (stalled / total) if total else 0.0
        score = round(0.55 * abandon + 0.25 * dwell + 0.20 * stall_rate, 4)
        ranked.append({**stage, "friction_score": score, "_index": index})
    ranked.sort(key=lambda row: (-row["friction_score"], -_count(row.get("stalled")), row["_index"]))
    return ranked[:limit]


def _stage_document(stage: dict[str, Any], why: dict[str, Any] | None, collector: _Collector) -> dict[str, Any]:
    key = str(stage["key"])
    metrics: dict[str, Any] = {
        "reached": collector.add(
            f"stage:{key}:count",
            stage=key,
            metric="count",
            value=_count(stage.get("count")),
            unit="workspaces",
        ),
    }
    previous = stage.get("from_previous")
    if previous is not None:
        ratio = round(float(previous), 4)
        metrics["from_previous"] = collector.add(
            f"stage:{key}:from_previous",
            stage=key,
            metric="from_previous",
            value=ratio,
            unit="ratio",
        )
        metrics["from_previous_pct"] = collector.add(
            f"stage:{key}:from_previous_pct",
            stage=key,
            metric="from_previous_pct",
            value=round(ratio * 100, 1),
            unit="percent",
        )
    from_start = stage.get("from_start")
    if from_start is not None:
        metrics["from_start"] = collector.add(
            f"stage:{key}:from_start",
            stage=key,
            metric="from_start",
            value=round(float(from_start), 4),
            unit="ratio",
        )
    metrics["stalled"] = collector.add(
        f"stage:{key}:stalled",
        stage=key,
        metric="stalled",
        value=_count(stage.get("stalled")),
        unit="workspaces",
    )
    if stage.get("median_seconds") is not None:
        metrics["median_seconds"] = collector.add(
            f"stage:{key}:median_seconds",
            stage=key,
            metric="median_seconds",
            value=round(float(stage["median_seconds"]), 2),
            unit="seconds",
        )
    if stage.get("p90_seconds") is not None:
        metrics["p90_seconds"] = collector.add(
            f"stage:{key}:p90_seconds",
            stage=key,
            metric="p90_seconds",
            value=round(float(stage["p90_seconds"]), 2),
            unit="seconds",
        )
    metrics["friction_score"] = collector.add(
        f"stage:{key}:friction",
        stage=key,
        metric="friction_score",
        value=float(stage.get("friction_score") or 0.0),
        unit="score",
    )

    section: dict[str, Any] = {
        "validation_failures": [],
        "network_failures": [],
        "dead_clicks": [],
        "rage_clicks": [],
        "survey": [],
        "dwell_p90_ms": None,
    }
    if why:
        for row in why.get("validation_failures") or []:
            form = _safe_key(row.get("form"))
            field = _safe_key(row.get("field"))
            rule = _safe_key(row.get("rule"))
            count = _count(row.get("count"))
            if not (form and field and rule and count):
                continue
            evidence_id = f"why:{key}:validation:{form}.{field}.{rule}"
            metrics_row = collector.add(
                evidence_id, stage=key, metric="validation_failure", value=count, unit="events"
            )
            section["validation_failures"].append(
                {"id": metrics_row["id"], "form": form, "field": field, "rule": rule, "count": count}
            )
        for row in why.get("network_failures") or []:
            endpoint = _safe_key(row.get("endpoint_key"))
            status = _safe_key(row.get("status"))
            count = _count(row.get("count"))
            if not (endpoint and status and count):
                continue
            evidence_id = f"why:{key}:network:{endpoint}:{status}"
            context = [int(status)] if status.isdigit() else None
            metrics_row = collector.add(
                evidence_id,
                stage=key,
                metric="network_failure",
                value=count,
                unit="events",
                context=context,
            )
            section["network_failures"].append(
                {"id": metrics_row["id"], "endpoint_key": endpoint, "status": status, "count": count}
            )
        for field_name, metric in (("dead_clicks", "dead_click"), ("rage_clicks", "rage_click")):
            for row in why.get(field_name) or []:
                element = _safe_key(row.get("element_key"))
                count = _count(row.get("count"))
                if not (element and count):
                    continue
                kind = "dead" if metric == "dead_click" else "rage"
                evidence_id = f"why:{key}:{kind}:{element}"
                metrics_row = collector.add(
                    evidence_id, stage=key, metric=metric, value=count, unit="events"
                )
                section[field_name].append({"id": metrics_row["id"], "element_key": element, "count": count})
        survey_counts: dict[str, int] = {}
        for row in why.get("survey") or []:
            raw = str(row.get("answer") or "").strip().lower()
            if not raw:
                continue
            code = raw if raw in SURVEY_CODES else SURVEY_OTHER
            survey_counts[code] = survey_counts.get(code, 0) + _count(row.get("count"))
        for code in sorted(survey_counts, key=lambda value: (-survey_counts[value], value)):
            count = survey_counts[code]
            if not count:
                continue
            evidence_id = f"why:{key}:survey:{code}"
            metrics_row = collector.add(
                evidence_id, stage=key, metric="survey_answer", value=count, unit="answers"
            )
            section["survey"].append({"id": metrics_row["id"], "answer": code, "count": count})
        dwell = why.get("dwell") or {}
        if dwell.get("p90_ms") is not None:
            p90_ms = round(float(dwell["p90_ms"]), 2)
            metrics_row = collector.add(
                f"why:{key}:dwell:p90",
                stage=key,
                metric="dwell_p90",
                value=p90_ms,
                unit="ms",
            )
            section["dwell_p90_ms"] = {"id": metrics_row["id"], "value": p90_ms}

    return {"key": key, "label": str(stage.get("label") or key), "metrics": metrics, "why": section}


def assemble_evidence(
    *,
    funnel: dict[str, Any],
    why_by_stage: dict[str, dict[str, Any]],
    window_days: int,
    window_start: datetime,
    window_end: datetime,
    event_count: int,
) -> dict[str, Any]:
    """Build the evidence document that is both prompted and validated against.

    Pure and deterministic: same inputs, same ids, same ``input_hash``. That is
    what makes the id set trustworthy enough to reject a model citation.
    """
    total = _count(funnel.get("total"))
    events = _count(event_count)
    collector = _Collector()
    cohort_metrics = {
        "total": collector.add(
            "cohort:total", stage=None, metric="count", value=total, unit="workspaces"
        ),
        "events": collector.add(
            "cohort:events", stage=None, metric="count", value=events, unit="events"
        ),
    }

    insufficient_reason: str | None = None
    if total == 0:
        insufficient_reason = "No workspaces were created in this window."
    elif events < MIN_EVENTS:
        insufficient_reason = (
            f"Only {events} telemetry events in this window; at least {MIN_EVENTS} are needed."
        )

    stages: list[dict[str, Any]] = []
    if insufficient_reason is None:
        for stage in _rank_stages(funnel):
            stages.append(_stage_document(stage, why_by_stage.get(stage["key"]), collector))

    document: dict[str, Any] = {
        "prompt_version": PROMPT_VERSION,
        "window": {
            "days": int(window_days),
            "start": window_start.astimezone(timezone.utc).date().isoformat(),
            "end": window_end.astimezone(timezone.utc).date().isoformat(),
        },
        "cohort": {"metrics": cohort_metrics, "total": total, "events": events},
        "stages": stages,
        "evidence": collector.items,
        "insufficient": insufficient_reason is not None,
    }
    if insufficient_reason is not None:
        document["insufficient_reason"] = insufficient_reason
    document["input_hash"] = _hash(document)
    return document


async def build_activation_evidence(db: AsyncSession, *, days: int = 30) -> dict[str, Any]:
    """Fetch the funnel, rank stages, and pull the why aggregates for the top 5.

    The why queries only run once the window has enough evidence; a quiet window
    returns immediately so the endpoint can store an "insufficient" insight
    without touching a provider.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    funnel = await build_funnel(db, days=days)
    events = await db.scalar(
        text("SELECT count(*) FROM analytics_events WHERE occurred_at >= :since"),
        {"since": since},
    )
    total = _count(funnel.get("total"))
    event_count = _count(events)
    why_by_stage: dict[str, dict[str, Any]] = {}
    if total > 0 and event_count >= MIN_EVENTS:
        for stage in _rank_stages(funnel):
            why_by_stage[stage["key"]] = await build_stage_why(db, stage=stage["key"], days=days)
    return assemble_evidence(
        funnel=funnel,
        why_by_stage=why_by_stage,
        window_days=days,
        window_start=since,
        window_end=now,
        event_count=event_count,
    )


def prompt_document(evidence: dict[str, Any]) -> dict[str, Any]:
    """The provider payload: inline ids only, no duplicate flat list, no hash."""
    return {
        "prompt_version": evidence["prompt_version"],
        "window": evidence["window"],
        "cohort": evidence["cohort"],
        "stages": evidence["stages"],
        "insufficient": evidence["insufficient"],
    }


def _parse_json(raw: str) -> dict[str, Any] | None:
    text_value = (raw or "").strip()
    if not text_value:
        return None
    if text_value.startswith("```"):
        # Tolerate a fenced block, but not prose around the JSON: a claim that
        # cannot be parsed must go through the repair attempt.
        text_value = text_value.strip("`").strip()
        if text_value.lower().startswith("json"):
            text_value = text_value[4:].strip()
    try:
        payload = json.loads(text_value)
    except (ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _number_forms(value: Any) -> set[float]:
    forms: set[float] = set()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return forms
    number = float(value)
    forms.add(round(number, 2))
    forms.add(float(round(number)))
    if 0.0 <= number <= 1.0:
        # Ratio evidence is commonly narrated as a percentage in either
        # direction ("82% continued", "18% dropped"); both are deterministic.
        forms.add(round(number * 100, 2))
        forms.add(round((1.0 - number) * 100, 2))
    return forms


def _unsupported_number(claim: str, cited: list[str], by_id: dict[str, dict[str, Any]]) -> str | None:
    """Reject a figure that is not one of the cited evidence values.

    Small ordinals (ranks, "top 5") and years are ignored; everything else must
    resolve to a cited value (or its percent form). This is a lexical check, not
    a proof: it stops invented counts without pretending to understand prose.
    """
    allowed: set[float] = set()
    for evidence_id in cited:
        item = by_id.get(evidence_id) or {}
        allowed |= _number_forms(item.get("value"))
        for extra in item.get("context") or []:
            allowed |= _number_forms(extra)
    for token in _NUMBER.findall(claim):
        try:
            number = float(token.replace(",", ""))
        except ValueError:
            continue
        if number <= 10 or 1900 <= number <= 2100:
            continue
        if not any(abs(number - candidate) < 0.011 for candidate in allowed):
            return token
    return None


def validate_digest(raw: str, evidence: dict[str, Any]) -> ValidationResult:
    """Validate a model reply against the evidence it was given.

    Rejected: non-JSON, missing/unknown stage, unknown evidence id, an uncited
    finding, a bad severity/confidence, or a number not present in the cited
    evidence. The caller retries once, then falls back to rules.
    """
    payload = _parse_json(raw)
    if payload is None:
        return ValidationResult(None, "Reply is not a JSON object.")

    by_id = {str(item["id"]): item for item in evidence.get("evidence") or []}
    allowed_stages = {str(stage["key"]) for stage in evidence.get("stages") or []}

    headline = payload.get("headline")
    if not isinstance(headline, str) or not headline.strip():
        return ValidationResult(None, "headline must be a non-empty string.")

    findings = payload.get("findings")
    if not isinstance(findings, list):
        return ValidationResult(None, "findings must be a list.")
    if len(findings) > 10:
        return ValidationResult(None, "findings must contain at most ten items.")

    for index, finding in enumerate(findings):
        label = f"findings[{index}]"
        if not isinstance(finding, dict):
            return ValidationResult(None, f"{label} must be an object.")
        stage = finding.get("stage")
        if not isinstance(stage, str) or stage not in allowed_stages:
            return ValidationResult(None, f"{label}.stage is not a stage in the evidence.")
        severity = finding.get("severity")
        if severity not in SEVERITIES:
            return ValidationResult(None, f"{label}.severity must be low, medium or high.")
        claim = finding.get("claim")
        if not isinstance(claim, str) or not claim.strip():
            return ValidationResult(None, f"{label}.claim must be a non-empty string.")
        if len(claim) > MAX_CLAIM_CHARS:
            return ValidationResult(None, f"{label}.claim is longer than {MAX_CLAIM_CHARS} characters.")
        cited = finding.get("evidence")
        if not isinstance(cited, list) or not cited:
            return ValidationResult(None, f"{label} cites no evidence.")
        if any(not isinstance(item, str) for item in cited):
            return ValidationResult(None, f"{label}.evidence must be a list of ids.")
        unknown = [item for item in cited if item not in by_id]
        if unknown:
            return ValidationResult(None, f"{label} cites an evidence id that is not in the input: {unknown[0]}")
        confidence = finding.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            return ValidationResult(None, f"{label}.confidence must be a number.")
        if not 0.0 <= float(confidence) <= 1.0:
            return ValidationResult(None, f"{label}.confidence must be between 0 and 1.")
        unsupported = _unsupported_number(finding["claim"], cited, by_id)
        if unsupported is not None:
            return ValidationResult(
                None, f"{label}.claim uses a number that is not in the cited evidence: {unsupported}"
            )

    focus = payload.get("recommended_focus")
    if not isinstance(focus, str):
        return ValidationResult(None, "recommended_focus must be a string.")
    if focus and focus not in allowed_stages:
        return ValidationResult(None, "recommended_focus is not a stage in the evidence.")

    if not isinstance(payload.get("insufficient_evidence"), bool):
        return ValidationResult(None, "insufficient_evidence must be a boolean.")
    return ValidationResult(payload)


def _severity_for(drop: float, signal: int) -> str:
    if drop >= 0.5 or signal >= 50:
        return "high"
    if drop >= 0.2 or signal >= 10:
        return "medium"
    return "low"


def _strongest_signal(stage: dict[str, Any]) -> tuple[str, list[str]] | None:
    """The single most useful deterministic signal on a stage, with its citations."""
    why = stage.get("why") or {}
    candidates: list[tuple[int, str, list[str]]] = []
    validation = why.get("validation_failures") or []
    if validation:
        top = max(validation, key=lambda row: int(row.get("count") or 0))
        candidates.append(
            (
                int(top.get("count") or 0),
                f"{int(top.get('count') or 0)} validation failures on {top['form']}.{top['field']} ({top['rule']}).",
                [str(top["id"])],
            )
        )
    network = why.get("network_failures") or []
    if network:
        top = max(network, key=lambda row: int(row.get("count") or 0))
        candidates.append(
            (
                int(top.get("count") or 0),
                f"{int(top.get('count') or 0)} failed requests to {top['endpoint_key']} (status {top['status']}).",
                [str(top["id"])],
            )
        )
    dead = why.get("dead_clicks") or []
    if dead:
        top = max(dead, key=lambda row: int(row.get("count") or 0))
        candidates.append(
            (
                int(top.get("count") or 0),
                f"{int(top.get('count') or 0)} dead clicks on {top['element_key']}.",
                [str(top["id"])],
            )
        )
    survey = why.get("survey") or []
    if survey:
        top = max(survey, key=lambda row: int(row.get("count") or 0))
        candidates.append(
            (
                int(top.get("count") or 0),
                f"{int(top.get('count') or 0)} merchants answered \"{top['answer']}\" on this step.",
                [str(top["id"])],
            )
        )
    dwell = why.get("dwell_p90_ms") or {}
    if dwell.get("value") is not None and float(dwell["value"]) >= 60_000:
        candidates.append(
            (
                int(float(dwell["value"]) // 1000),
                f"The p90 dwell on this stage's routes is {float(dwell['value']):g} ms.",
                [str(dwell["id"])],
            )
        )
    if not candidates:
        return None
    return max(candidates, key=lambda row: row[0])


def fallback_digest(evidence: dict[str, Any]) -> dict[str, Any]:
    """Deterministic rules digest, used when the provider fails or lies.

    Every sentence is assembled from evidence values and every finding cites the
    ids it was built from, so a fallback is useful and auditable rather than a
    placeholder. Confidence is fixed at 0.4 because rules rank, they do not
    interpret.
    """
    findings: list[dict[str, Any]] = []
    for stage in (evidence.get("stages") or [])[:3]:
        previous = (stage.get("metrics", {}).get("from_previous") or {}).get("value")
        drop = 0.0 if previous is None else max(0.0, 1.0 - float(previous))
        signal = _strongest_signal(stage)
        if drop < 0.1 and signal is None:
            continue
        citations: list[str] = []
        sentences: list[str] = []
        if drop >= 0.1 and previous is not None:
            pct_metric = stage["metrics"].get("from_previous_pct") or {}
            stalled = int((stage.get("metrics", {}).get("stalled") or {}).get("value") or 0)
            sentences.append(
                f"{pct_metric.get('value')}% of the previous stage continued; {stalled} workspaces stalled here."
            )
            citations.extend(
                [
                    str(pct_metric.get("id") or stage["metrics"]["from_previous"]["id"]),
                    str(stage["metrics"]["stalled"]["id"]),
                ]
            )
        if signal is not None:
            _, claim, ids = signal
            sentences.append(claim)
            citations.extend(ids)
        if not sentences:
            continue
        findings.append(
            {
                "stage": stage["key"],
                "severity": _severity_for(drop, signal[0] if signal else 0),
                "claim": " ".join(sentences),
                "evidence": list(dict.fromkeys(citations)),
                "confidence": 0.4,
            }
        )
    if findings:
        focus_stage = next(
            (stage for stage in evidence.get("stages") or [] if stage["key"] == findings[0]["stage"]),
            None,
        )
        label = (focus_stage or {}).get("label") or findings[0]["stage"]
        headline = f"{label} is the largest friction point in this window"
    else:
        headline = "No stage shows material friction in this window"
    return {
        "headline": headline,
        "findings": findings,
        "recommended_focus": findings[0]["stage"] if findings else "",
        "insufficient_evidence": False,
    }


def _worst_severity(payload: dict[str, Any]) -> str:
    severities = [finding.get("severity") for finding in payload.get("findings") or []]
    return max(severities, key=lambda value: _SEVERITY_RANK.get(value, 0), default="low")


def _average_confidence(payload: dict[str, Any]) -> float | None:
    scores = [
        float(finding["confidence"])
        for finding in payload.get("findings") or []
        if isinstance(finding.get("confidence"), (int, float))
    ]
    return round(sum(scores) / len(scores), 2) if scores else None


def _summarize(payload: dict[str, Any], evidence: dict[str, Any]) -> str:
    if payload.get("insufficient_evidence"):
        return str(payload.get("reason") or "Not enough evidence yet.")
    findings = payload.get("findings") or []
    if not findings:
        return "No material friction found: no ranked stage lost a meaningful share of the previous stage."
    focus = payload.get("recommended_focus") or ""
    label = {}
    for stage in evidence.get("stages") or []:
        label[str(stage["key"])] = str(stage.get("label") or stage["key"])
    focus_label = label.get(focus, focus or "none")
    return f"{len(findings)} cited finding{'s' if len(findings) != 1 else ''}. Recommended focus: {focus_label}."


def _insight_row(
    evidence: dict[str, Any],
    payload: dict[str, Any],
    *,
    validator: str,
    provider: str | None,
    model: str | None,
) -> AIInsight:
    focus = payload.get("recommended_focus") or ""
    stages = {str(stage["key"]) for stage in evidence.get("stages") or []}
    return AIInsight(
        kind=KIND,
        window_days=int(evidence["window"]["days"]),
        stage_key=focus if focus in stages else None,
        title=str(payload.get("headline") or "Activation digest")[:MAX_TITLE_CHARS],
        summary=_summarize(payload, evidence),
        severity=_worst_severity(payload),
        confidence=_average_confidence(payload),
        evidence=evidence.get("evidence") or [],
        payload=payload,
        prompt_version=PROMPT_VERSION,
        provider=provider,
        model=model,
        input_hash=str(evidence["input_hash"]),
        validator=validator,
    )


async def generate_digest(db: AsyncSession, *, days: int = 30) -> AIInsight:
    """Generate, validate and store one digest for the window.

    Raises :class:`ActivationAIDisabled` when the kill switch is off and
    ``AINotConfiguredError`` when no provider/key exists (the endpoint maps both
    to an explicit 4xx/5xx). Provider failure is *not* an exception: the rules
    digest is stored and labelled ``fallback``.
    """
    if not settings.activation_ai_enabled:
        raise ActivationAIDisabled(
            "AI digest generation is disabled (ACTIVATION_AI_ENABLED=false)."
        )

    evidence = await build_activation_evidence(db, days=days)
    if evidence["insufficient"]:
        payload = {
            "headline": "Not enough evidence yet",
            "findings": [],
            "recommended_focus": "",
            "insufficient_evidence": True,
            "reason": evidence.get("insufficient_reason") or "Not enough evidence yet.",
        }
        insight = _insight_row(
            evidence, payload, validator="insufficient", provider=None, model=None
        )
        db.add(insight)
        await db.commit()
        await db.refresh(insight)
        return insight

    # A setup problem is the operator's to fix; surface it before any spend.
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
                prompt_document(evidence), sort_keys=True, separators=(",", ":")
            ),
        }
    ]

    async def attempt(conversation: list[dict[str, str]]) -> tuple[str, dict[str, int]]:
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
            # Record the latency of the failed attempt too; the caller decides
            # whether it is a setup problem or a billable provider failure.
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
        return str(result.get("content") or ""), usage

    try:
        raw, _ = await attempt(messages)
        outcome = validate_digest(raw, evidence)
        if outcome.ok:
            payload = outcome.payload
        else:
            runs[-1]["outcome"] = "parse_error"
            # One repair turn: the rejected reply is shown back with the reason,
            # which is far more effective than repeating the same prompt.
            repair = [
                *messages,
                {"role": "assistant", "content": raw[:6000]},
                {"role": "user", "content": REPAIR_PROMPT.format(error=outcome.error or "invalid JSON")},
            ]
            repaired_raw, _ = await attempt(repair)
            repaired = validate_digest(repaired_raw, evidence)
            if repaired.ok:
                payload, validator = repaired.payload, "repaired"
            else:
                runs[-1]["outcome"] = "parse_error"
                payload, validator = fallback_digest(evidence), "fallback"
    except AINotConfiguredError:
        raise
    except AIError:
        payload, validator = fallback_digest(evidence), "fallback"

    if payload is None:  # defensive; the branches above always set it
        payload, validator = fallback_digest(evidence), "fallback"

    insight = _insight_row(
        evidence, payload, validator=validator, provider=provider, model=model_name
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
                cost_usd=round(estimate_cost_usd(model_used, prompt_tokens, completion_tokens, prices), 6),
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


async def latest_digest(db: AsyncSession, *, days: int = 30) -> AIInsight | None:
    """The most recent digest for one window, or ``None``."""
    return await db.scalar(
        select(AIInsight)
        .where(AIInsight.kind == KIND, AIInsight.window_days == int(days))
        .order_by(AIInsight.created_at.desc())
        .limit(1)
    )


async def decide_digest(
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
