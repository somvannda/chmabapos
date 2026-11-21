"""Deterministic step review: where the setup journey loops, stalls and leaks.

This module is the *only* source of numbers for the step reducer. It answers
four questions from telemetry alone:

1. **Where do sessions go next?** A route transition matrix, counted by distinct
   session, never by event. A session that renders ``setup.plan`` five times is
   one session moving through the journey, not five.
2. **Where do they loop or go back?** ``A -> B -> A`` triples and transitions to
   a route the session already visited. Both are signals that a screen is doing
   work the merchant did not expect.
3. **How much does each step cost?** Reached/completed sessions, median and p90
   dwell, back rate and marginal conversion for the three setup screens and the
   product-create screen.
4. **Is there enough data to say anything?** Under :data:`MIN_SESSIONS` the
   review is empty with a reason, and the AI layer must not be called.

The AI layer in :mod:`app.services.step_review_ai` may only rank and explain
these values. It cannot change a step key, invent an evidence id, or produce a
number that is not in :func:`build_evidence`.

Privacy: the document contains route keys, step keys, fixed survey codes and
aggregate counts. It never selects a user id, company id, email, name, URL, IP
or free-text property. The stage/route keys are already registry-owned, and
anything that does not look like one is dropped rather than prompted.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.activation_ai import _safe_key

# The three setup screens, in funnel order, then the first product screen.
SETUP_STEPS: tuple[str, ...] = ("setup.company", "setup.questions", "setup.plan")
PRODUCT_STEP = "products"
TRACKED_STEPS: tuple[str, ...] = (*SETUP_STEPS, PRODUCT_STEP)

STEP_LABELS: dict[str, str] = {
    "setup.company": "Company details",
    "setup.questions": "A few quick questions",
    "setup.plan": "Choose your plan",
    "products": "Create a product",
}

# apps/web/src/features/onboarding.jsx: ONBOARDING_STEPS, one-based.
STEP_NUMBERS: dict[str, int] = {"setup.company": 1, "setup.questions": 2, "setup.plan": 3}

# The canonical forward order. A transition to a lower number is a backtrack.
ROUTE_ORDER: dict[str, int] = {
    "landing": 0,
    "signup": 1,
    "login": 2,
    "setup.company": 3,
    "setup.questions": 4,
    "setup.plan": 5,
    "dashboard": 6,
    "products": 7,
    "pos": 8,
    "orders": 9,
}

# Fixed codes from apps/web/src/lib/abandonSurvey.js. "Other" free text is
# bucketed and never reproduced.
SURVEY_CODES = frozenset({"thinking", "unclear", "broken", "expensive"})
SURVEY_OTHER = "other"

# A step review is an opinion about behaviour, so it needs a real sample.
MIN_SESSIONS = 30
TOP_TRANSITIONS = 20
TOP_LOOPS = 10
TOP_BACKTRACKS = 10

# Properties that would prove a merchant changed a defaulted answer. The
# registry does not emit one today, so this is normally ``None`` and the UI says
# "not measured" instead of inventing a percentage.
DEFAULT_CHANGED_FLAGS = ("changed", "answer_changed", "edited", "default_changed")

# A session is excluded when the session row is marked internal or its user is
# platform staff. The same rule the funnel and stage drilldown use.
_SCOPE = """
    e.occurred_at >= :since
    AND (
        e.session_id IS NULL
        OR NOT EXISTS (
            SELECT 1 FROM analytics_sessions s
            WHERE s.id = e.session_id AND s.is_internal
        )
    )
    AND NOT EXISTS (
        SELECT 1 FROM users u
        WHERE u.id = e.user_id AND u.platform_role IS NOT NULL
    )
"""

_ROUTES_SQL = f"""
WITH ordered AS (
    SELECT e.session_id,
           e.route_key,
           e.occurred_at,
           e.id,
           lag(e.route_key) OVER (
               PARTITION BY e.session_id ORDER BY e.occurred_at, e.id
           ) AS previous_route
    FROM analytics_events e
    WHERE {_SCOPE}
      AND e.session_id IS NOT NULL
      AND e.route_key IS NOT NULL
      AND e.name IN (
          'page.viewed',
          'onboarding.step_viewed',
          'onboarding.step_completed',
          'onboarding.step_back',
          'product.create_opened'
      )
)
SELECT session_id, route_key, occurred_at, id
FROM ordered
WHERE previous_route IS DISTINCT FROM route_key
ORDER BY session_id, occurred_at, id
"""

_SESSIONS_SQL = """
SELECT s.id, s.user_id, s.company_id
FROM analytics_sessions s
WHERE s.id = ANY(CAST(:ids AS uuid[]))
  AND NOT s.is_internal
  AND NOT EXISTS (
      SELECT 1 FROM users u
      WHERE u.id = s.user_id AND u.platform_role IS NOT NULL
  )
"""

_CONVERSIONS_SQL = """
SELECT DISTINCT e.user_id, e.company_id
FROM analytics_events e
WHERE e.name = 'workspace.created'
  AND e.occurred_at >= :since
  AND NOT EXISTS (
      SELECT 1 FROM users u
      WHERE u.id = e.user_id AND u.platform_role IS NOT NULL
  )
"""

_STEP_EVENTS_SQL = f"""
SELECT e.session_id, e.name, e.route_key, e.duration_ms, e.properties, e.occurred_at
FROM analytics_events e
WHERE {_SCOPE}
  AND e.session_id = ANY(CAST(:ids AS uuid[]))
  AND e.name IN (
      'onboarding.step_viewed',
      'onboarding.step_completed',
      'onboarding.step_back',
      'onboarding.abandon_survey',
      'page.left',
      'product.create_opened',
      'product.created'
  )
ORDER BY e.session_id, e.occurred_at, e.id
"""


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(int(quantile * (len(ordered) - 1)), len(ordered) - 1)
    return round(ordered[index], 2)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _step_number(properties: dict[str, Any] | None) -> int | None:
    if not isinstance(properties, dict):
        return None
    number = _number(properties.get("step"))
    return int(number) if number is not None else None


def _top(counts: dict[tuple[str, str], set[str]], *, limit: int) -> list[dict[str, Any]]:
    ordered = sorted(counts.items(), key=lambda pair: (-len(pair[1]), pair[0][0], pair[0][1]))
    return [
        {"from": source, "to": target, "sessions": len(sessions)}
        for (source, target), sessions in ordered[:limit]
    ]


def transition_matrix(sequences: dict[str, list[str]]) -> tuple[list[dict], list[dict], list[dict]]:
    """Route transitions, ``A -> B -> A`` loops and backtracks, by session.

    ``sequences`` maps a session id to its *collapsed* route sequence (adjacent
    repeats removed). Each edge is stored as a set of session ids, so the same
    session clicking through the same pair twice is still one session. Loops are
    consecutive triples where the first and third routes match. A backtrack is a
    transition to any route the session already visited before the source.
    """
    transitions: dict[tuple[str, str], set[str]] = defaultdict(set)
    loops: dict[tuple[str, str], set[str]] = defaultdict(set)
    backtracks: dict[tuple[str, str], set[str]] = defaultdict(set)

    for session_id, raw_sequence in sequences.items():
        # A client controls ``route_key``, so anything that is not a code-shaped
        # registry key is dropped before it can reach a count or a prompt.
        sequence = [key for key in (_safe_key(route) for route in raw_sequence) if key]
        if not sequence:
            continue
        for index in range(1, len(sequence)):
            source, target = sequence[index - 1], sequence[index]
            if source == target:
                continue
            transitions[(source, target)].add(session_id)
            if index >= 2 and sequence[index - 2] == target:
                loops[(sequence[index - 2], source)].add(session_id)

        seen: set[str] = set()
        previous: str | None = None
        for route in sequence:
            if previous is not None and route != previous and route in seen:
                backtracks[(previous, route)].add(session_id)
            seen.add(route)
            previous = route

    loop_rows = [
        {"from": source, "to": target, "key": f"{source}->{target}->{source}", "sessions": len(sessions)}
        for (source, target), sessions in sorted(
            loops.items(), key=lambda pair: (-len(pair[1]), pair[0][0], pair[0][1])
        )[:TOP_LOOPS]
    ]
    return (
        _top(transitions, limit=TOP_TRANSITIONS),
        loop_rows,
        _top(backtracks, limit=TOP_BACKTRACKS),
    )


def marginal_conversion(
    reached: set[str],
    sessions: set[str],
    converted: set[str],
) -> float | None:
    """Conversion with the step minus conversion without it, capped to [-1, 1].

    ``converted`` is the set of sessions whose owner created a workspace in the
    window. Let ``R`` be sessions that reached the step and ``N = sessions - R``
    the sessions that did not (both restricted to sessions with route activity):

        marginal = |R & converted| / |R| - |N & converted| / |N|

    A positive value means reaching the step is associated with a *higher*
    downstream conversion; a negative value means the step is associated with a
    lower one. This is association, not causation: sessions that reach a later
    step are already conditioned on surviving the earlier ones. It exists to
    rank candidates for an experiment, which is why a removal is never proposed
    when this value is ``None`` (one side of the comparison had no sessions).
    """
    reached = set(reached)
    sessions = set(sessions)
    converted = set(converted)
    not_reached = sessions - reached
    if not reached or not not_reached:
        return None
    with_step = len(reached & converted) / len(reached)
    without_step = len(not_reached & converted) / len(not_reached)
    return round(max(-1.0, min(1.0, with_step - without_step)), 4)


def _reached(step: str, sequence: list[str], events: list[dict[str, Any]]) -> bool:
    if step in sequence:
        return True
    number = STEP_NUMBERS.get(step)
    if number is not None:
        return any(
            event.get("name") == "onboarding.step_viewed"
            and _step_number(event.get("properties")) == number
            for event in events
        )
    if step == PRODUCT_STEP:
        return any(event.get("name") == "product.create_opened" for event in events)
    return False


def _completed(
    step: str,
    sequence: list[str],
    events: list[dict[str, Any]],
    converted: bool,
) -> bool:
    if step != PRODUCT_STEP and converted:
        return True
    order = ROUTE_ORDER.get(step)
    if order is not None and step in sequence:
        first = sequence.index(step)
        if any(ROUTE_ORDER.get(route, order) > order for route in sequence[first + 1 :]):
            return True
    if step == PRODUCT_STEP:
        return any(event.get("name") == "product.created" for event in events)
    number = STEP_NUMBERS.get(step)
    return any(
        event.get("name") == "onboarding.step_completed"
        and _step_number(event.get("properties")) == number
        for event in events
    )


def _dwell_samples(step: str, events: list[dict[str, Any]]) -> list[float]:
    number = STEP_NUMBERS.get(step)
    samples: list[float] = []
    for event in events:
        name = event.get("name")
        properties = event.get("properties") or {}
        value: float | None = None
        if name == "page.left" and event.get("route_key") == step:
            value = _number(properties.get("dwell_ms"))
            if value is None:
                value = _number(event.get("duration_ms"))
        elif (
            number is not None
            and name == "onboarding.step_completed"
            and _step_number(properties) == number
        ):
            value = _number(event.get("duration_ms"))
            if value is None:
                value = _number(properties.get("duration_ms"))
        elif step == PRODUCT_STEP and name == "product.created":
            value = _number(event.get("duration_ms"))
            if value is None:
                value = _number(properties.get("duration_ms"))
        if value is not None and value >= 0:
            samples.append(value)
    return samples


def _went_back(step: str, sequence: list[str], events: list[dict[str, Any]]) -> bool:
    number = STEP_NUMBERS.get(step)
    if number is not None:
        if any(
            event.get("name") == "onboarding.step_back"
            and _step_number({"step": (event.get("properties") or {}).get("from_step")}) == number
            for event in events
        ):
            return True
    order = ROUTE_ORDER.get(step)
    if order is None:
        return False
    previous: str | None = None
    for route in sequence:
        if previous == step and route != step and ROUTE_ORDER.get(route, order) < order:
            return True
        previous = route
    return False


def _default_acceptance(step: str, events: list[dict[str, Any]]) -> float | None:
    """Share of answered sessions that changed a defaulted answer, or ``None``.

    Only sessions whose ``onboarding.step_completed`` event carries one of
    :data:`DEFAULT_CHANGED_FLAGS` can be classified. When the registry emits
    none of them the honest answer is "not measured", not zero.
    """
    number = STEP_NUMBERS.get(step)
    if number is None:
        return None
    answered = 0
    changed = 0
    for event in events:
        if event.get("name") != "onboarding.step_completed":
            continue
        properties = event.get("properties") or {}
        if _step_number(properties) != number:
            continue
        flags = [properties[key] for key in DEFAULT_CHANGED_FLAGS if key in properties]
        if not flags:
            continue
        answered += 1
        if any(bool(flag) for flag in flags):
            changed += 1
    return round(changed / answered, 4) if answered else None


def _converted_sessions(
    sessions: dict[str, dict[str, Any]],
    converted_users: set[str],
    converted_companies: set[str],
) -> set[str]:
    converted: set[str] = set()
    for session_id, identity in sessions.items():
        user_id = identity.get("user_id")
        company_id = identity.get("company_id")
        if (user_id and str(user_id) in converted_users) or (
            company_id and str(company_id) in converted_companies
        ):
            converted.add(session_id)
    return converted


def _step_rows(
    sequences: dict[str, list[str]],
    sessions: dict[str, dict[str, Any]],
    events_by_session: dict[str, list[dict[str, Any]]],
    converted: set[str],
) -> list[dict[str, Any]]:
    all_sessions = set(sequences)
    rows: list[dict[str, Any]] = []
    for step in TRACKED_STEPS:
        reached: set[str] = set()
        completed: set[str] = set()
        back: set[str] = set()
        dwell: list[float] = []
        for session_id, sequence in sequences.items():
            events = events_by_session.get(session_id, [])
            if not _reached(step, sequence, events):
                continue
            reached.add(session_id)
            if _completed(step, sequence, events, session_id in converted):
                completed.add(session_id)
            if _went_back(step, sequence, events):
                back.add(session_id)
            dwell.extend(_dwell_samples(step, events))
        rows.append(
            {
                "key": step,
                "label": STEP_LABELS[step],
                "reached_sessions": len(reached),
                "completed_sessions": len(completed),
                "completion_rate": round(len(completed) / len(reached), 4) if reached else None,
                "median_dwell_ms": _percentile(dwell, 0.5),
                "p90_dwell_ms": _percentile(dwell, 0.9),
                "dwell_samples": len(dwell),
                "back_sessions": len(back),
                "back_rate": round(len(back) / len(reached), 4) if reached else None,
                "marginal_conversion": marginal_conversion(reached, all_sessions, converted),
                "default_acceptance": _default_acceptance(
                    step, [event for sid in reached for event in events_by_session.get(sid, [])]
                ),
            }
        )
    return rows


def _survey_counts(events_by_session: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for events in events_by_session.values():
        for event in events:
            if event.get("name") != "onboarding.abandon_survey":
                continue
            answer = str((event.get("properties") or {}).get("answer") or "").strip().lower()
            if not answer:
                continue
            code = answer if answer in SURVEY_CODES else SURVEY_OTHER
            counts[code] = counts.get(code, 0) + 1
    return counts


def build_evidence(
    transitions: list[dict[str, Any]],
    loops: list[dict[str, Any]],
    backtracks: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    survey: dict[str, int],
) -> list[dict[str, Any]]:
    """The deterministic id set the AI may cite, and nothing else.

    Ids are stable across runs for the same data: a transition is
    ``trans:<from>-><to>``, a loop ``loop:<a>-><b>-><a>``, a backtrack
    ``back:<from>-><to>``, a step metric ``step:<key>:<metric>`` and a survey
    bucket ``survey:<code>``.
    """
    items: list[dict[str, Any]] = []
    for row in transitions:
        items.append(
            {
                "id": f"trans:{row['from']}->{row['to']}",
                "kind": "transition",
                "value": row["sessions"],
                "unit": "sessions",
            }
        )
    for row in loops:
        items.append(
            {
                "id": f"loop:{row['key']}",
                "kind": "loop",
                "value": row["sessions"],
                "unit": "sessions",
            }
        )
    for row in backtracks:
        items.append(
            {
                "id": f"back:{row['from']}->{row['to']}",
                "kind": "backtrack",
                "value": row["sessions"],
                "unit": "sessions",
            }
        )
    for row in steps:
        key = row["key"]
        metrics: list[tuple[str, Any, str]] = [
            ("reached", row["reached_sessions"], "sessions"),
            ("completed", row["completed_sessions"], "sessions"),
            ("dwell_median", row["median_dwell_ms"], "ms"),
            ("dwell_p90", row["p90_dwell_ms"], "ms"),
            ("back_rate", row["back_rate"], "ratio"),
            ("marginal", row["marginal_conversion"], "ratio"),
            ("default_acceptance", row["default_acceptance"], "ratio"),
        ]
        for metric, value, unit in metrics:
            if value is None:
                continue
            items.append(
                {
                    "id": f"step:{key}:{metric}",
                    "kind": "step",
                    "step_key": key,
                    "value": value,
                    "unit": unit,
                }
            )
    for code in sorted(survey, key=lambda value: (-survey[value], value)):
        items.append(
            {
                "id": f"survey:{code}",
                "kind": "survey",
                "value": survey[code],
                "unit": "answers",
            }
        )
    return items


def analyse_step_review(
    *,
    sequences: dict[str, list[str]],
    sessions: dict[str, dict[str, Any]],
    converted_users: set[str] | None = None,
    converted_companies: set[str] | None = None,
    events_by_session: dict[str, list[dict[str, Any]]] | None = None,
    window_days: int = 30,
) -> dict[str, Any]:
    """Build the whole deterministic review from session route sequences.

    Pure, so the unit tests exercise the same code the endpoint does. The only
    input that is not a plain value is ``sessions`` (user/company identity used
    to decide whether a session's owner created a workspace); ids never leave
    this function.
    """
    session_count = len(sequences)
    if session_count < MIN_SESSIONS:
        return {
            "window_days": window_days,
            "insufficient": True,
            "reason": (
                f"Only {session_count} session{'s' if session_count != 1 else ''} in this window; "
                f"at least {MIN_SESSIONS} are needed for a step review."
            ),
            "sessions": session_count,
            "transitions": [],
            "loops": [],
            "backtracks": [],
            "steps": [],
            "survey": [],
            "evidence": [],
        }

    events_by_session = events_by_session or {}
    transitions, loops, backtracks = transition_matrix(sequences)
    converted = _converted_sessions(
        sessions, converted_users or set(), converted_companies or set()
    )
    steps = _step_rows(sequences, sessions, events_by_session, converted)
    survey = _survey_counts(events_by_session)
    return {
        "window_days": window_days,
        "insufficient": False,
        "sessions": session_count,
        "transitions": transitions,
        "loops": loops,
        "backtracks": backtracks,
        "steps": steps,
        "survey": [{"code": code, "count": count} for code, count in survey.items()],
        "evidence": build_evidence(transitions, loops, backtracks, steps, survey),
    }


def _identity_rows(rows: list[Any]) -> dict[str, dict[str, Any]]:
    identities: dict[str, dict[str, Any]] = {}
    for row in rows:
        identities[str(row["id"])] = {
            "user_id": str(row["user_id"]) if row["user_id"] else None,
            "company_id": str(row["company_id"]) if row["company_id"] else None,
        }
    return identities


def _event_rows(rows: list[Any]) -> dict[str, list[dict[str, Any]]]:
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        events[str(row["session_id"])].append(
            {
                "name": row["name"],
                "route_key": row["route_key"],
                "duration_ms": row["duration_ms"],
                "properties": row["properties"] or {},
                "occurred_at": row["occurred_at"],
            }
        )
    return events


async def build_step_review(db: AsyncSession, *, days: int = 30) -> dict[str, Any]:
    """Load the window and return the deterministic step review.

    The route query collapses adjacent repeats in SQL, so Python only sees route
    *changes*. A quiet window returns before the identity, conversion and step
    queries run, which keeps the insufficient path cheap.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await db.execute(text(_ROUTES_SQL), {"since": since})).mappings().all()

    sequences: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        sequences[str(row["session_id"])].append(str(row["route_key"]))

    if len(sequences) < MIN_SESSIONS:
        return analyse_step_review(sequences={}, sessions={}, window_days=days) | {
            "sessions": len(sequences),
            "reason": (
                f"Only {len(sequences)} session{'s' if len(sequences) != 1 else ''} in this window; "
                f"at least {MIN_SESSIONS} are needed for a step review."
            ),
        }

    session_ids: list[UUID] = [UUID(session_id) for session_id in sequences]
    parameters = {"since": since, "ids": session_ids}

    identity_rows = (await db.execute(text(_SESSIONS_SQL), {"ids": session_ids})).mappings().all()
    conversion_rows = (await db.execute(text(_CONVERSIONS_SQL), {"since": since})).mappings().all()
    event_rows = (await db.execute(text(_STEP_EVENTS_SQL), parameters)).mappings().all()

    converted_users = {str(row["user_id"]) for row in conversion_rows if row["user_id"]}
    converted_companies = {str(row["company_id"]) for row in conversion_rows if row["company_id"]}

    return analyse_step_review(
        sequences=dict(sequences),
        sessions=_identity_rows(identity_rows),
        converted_users=converted_users,
        converted_companies=converted_companies,
        events_by_session=_event_rows(event_rows),
        window_days=days,
    )
