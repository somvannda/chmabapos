"""The read side that explains a funnel stage: why it leaks, and who stopped.

The cohort funnel in :mod:`app.services.activation` answers *where* merchants drop
off, using authoritative server milestones. This module answers the next two
questions for one stage:

1. **Why** - the validation errors, API failures, dead/rage clicks, dwell and
   one-question abandon-survey answers the merchant experienced on the routes
   that stage owns.
2. **Who** - the sessions whose last known route is one of those routes and that
   never reached a later milestone, plus the ordered timeline of any one session.

Design rules:

- Stage keys are a closed set. An unknown key is a client bug, so the service
  raises :class:`UnknownJourneyStage` and the route turns it into a 400 with the
  valid keys in the detail rather than returning an empty panel that looks like
  "no friction".
- Privacy is enforced in SQL, not in the handler: internal sessions and
  platform-role users never contribute to a count, and the timeline selects only
  the display columns (``anonymous_id``, ``ip_hash`` and ``user_agent`` are never
  read).
- Every list is grouped and capped, so the admin drawer renders the same shape
  whether the window has ten events or ten million.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Routes each stage is observed on. Client events carry a stable ``route_key``
# rather than a URL, so a route rename does not silently empty this report.
STAGE_ROUTES: dict[str, tuple[str, ...]] = {
    "account_created": ("signup", "login"),
    "email_verified": ("signup", "login"),
    "first_login": ("signup", "login"),
    "setup_opened": ("setup.company", "setup.questions", "setup.plan"),
    "workspace_created": ("setup.company", "setup.questions", "setup.plan"),
    "first_product": ("products",),
    "shift_opened": ("pos", "dashboard", "orders"),
    "first_sale": ("pos", "dashboard", "orders"),
}

# Funnel order, with the server milestone that proves a merchant got past the
# stage. ``setup_opened`` is client-only: the proof of progress is the workspace
# that follows it.
_STAGE_MILESTONES: tuple[tuple[str, str | None], ...] = (
    ("account_created", "user.registered"),
    ("email_verified", "user.email_verified"),
    ("first_login", "user.logged_in"),
    ("setup_opened", None),
    ("workspace_created", "workspace.created"),
    ("first_product", "product.created"),
    ("shift_opened", "shift.opened"),
    ("first_sale", "order.paid"),
)

_TOP_GROUPS = 10
_TIMELINE_LIMIT = 500

# Applied to every explanatory query. A session flagged internal, or owned by a
# platform-role account, is staff traffic and must never move a friction number.
_SCOPE = """
    e.occurred_at >= :since
    AND e.route_key = ANY(CAST(:routes AS text[]))
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


class UnknownJourneyStage(ValueError):
    """The requested stage is not one this report knows how to explain."""


def stage_routes(stage: str) -> tuple[str, ...]:
    """Routes for ``stage``, or a 400-worthy error listing the valid keys."""
    try:
        return STAGE_ROUTES[stage]
    except KeyError:
        known = ", ".join(STAGE_ROUTES)
        raise UnknownJourneyStage(
            f"Unknown stage '{stage}'. Valid stages: {known}."
        ) from None


def later_milestones(stage: str) -> tuple[str, ...]:
    """Server milestones that prove the merchant got beyond ``stage``."""
    keys = [key for key, _ in _STAGE_MILESTONES]
    names = [name for _, name in _STAGE_MILESTONES]
    index = keys.index(stage)
    return tuple(name for name in names[index + 1 :] if name)


def _window(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


async def _rows(db: AsyncSession, sql: str, parameters: dict[str, Any]) -> list[Any]:
    return (await db.execute(text(sql), parameters)).mappings().all()


async def build_stage_why(db: AsyncSession, *, stage: str, days: int = 30) -> dict[str, Any]:
    """Validation, network, click and dwell friction on a stage's routes.

    ``survey`` holds the top answers of the one-question abandon survey, with
    ``survey_total`` as their denominator. It is explanatory only: the funnel
    counts in :mod:`app.services.activation` never read it.
    """
    routes = stage_routes(stage)
    parameters = {"since": _window(days), "routes": list(routes), "limit": _TOP_GROUPS}

    validation = await _rows(
        db,
        f"""
        SELECT e.properties->>'form' AS form,
               e.properties->>'field' AS field,
               e.properties->>'rule' AS rule,
               count(*) AS count
        FROM analytics_events e
        WHERE {_SCOPE} AND e.name = 'ui.form_validation_failed'
        GROUP BY 1, 2, 3
        ORDER BY count DESC, form NULLS LAST, field NULLS LAST, rule NULLS LAST
        LIMIT :limit
        """,
        parameters,
    )
    network = await _rows(
        db,
        f"""
        SELECT e.route_key AS route_key,
               e.properties->>'endpoint_key' AS endpoint_key,
               e.properties->>'status' AS status,
               count(*) AS count
        FROM analytics_events e
        WHERE {_SCOPE} AND e.name = 'error.network'
        GROUP BY 1, 2, 3
        ORDER BY count DESC, route_key NULLS LAST, endpoint_key NULLS LAST, status NULLS LAST
        LIMIT :limit
        """,
        parameters,
    )
    dead_clicks = await _rows(
        db,
        f"""
        SELECT coalesce(e.element_key, e.properties->>'element_key') AS element_key,
               count(*) AS count
        FROM analytics_events e
        WHERE {_SCOPE} AND e.name = 'ui.dead_click'
        GROUP BY 1
        ORDER BY count DESC, element_key NULLS LAST
        LIMIT :limit
        """,
        parameters,
    )
    rage_clicks = await _rows(
        db,
        f"""
        SELECT coalesce(e.element_key, e.properties->>'element_key') AS element_key,
               count(*) AS count
        FROM analytics_events e
        WHERE {_SCOPE} AND e.name = 'ui.rage_click'
        GROUP BY 1
        ORDER BY count DESC, element_key NULLS LAST
        LIMIT :limit
        """,
        parameters,
    )
    # ``dwell_ms`` rides in properties, and a hand-written client could send a
    # non-numeric value; the regex keeps one bad row from failing the whole panel.
    dwell = (
        await db.execute(
            text(
                f"""
                SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY dwell) AS median_ms,
                       percentile_cont(0.9) WITHIN GROUP (ORDER BY dwell) AS p90_ms,
                       count(*) AS samples
                FROM (
                    SELECT (e.properties->>'dwell_ms')::numeric AS dwell
                    FROM analytics_events e
                    WHERE {_SCOPE}
                      AND e.name = 'page.left'
                      AND (e.properties->>'dwell_ms') ~ '^[0-9]+(\\.[0-9]+)?$'
                ) measured
                """
            ),
            parameters,
        )
    ).mappings().one()
    samples = (
        await db.execute(
            text(
                f"""
                SELECT count(*) AS events,
                       count(DISTINCT e.session_id) AS sessions
                FROM analytics_events e
                WHERE {_SCOPE}
                """
            ),
            parameters,
        )
    ).mappings().one()
    # The one-question abandon survey is the only human-readable "why" in the
    # panel. It is explanatory data: it never moves a funnel count, so it is
    # read here rather than in app.services.activation.
    survey = await _rows(
        db,
        f"""
        SELECT btrim(e.properties->>'answer') AS answer,
               count(*) AS count
        FROM analytics_events e
        WHERE {_SCOPE}
          AND e.name = 'onboarding.abandon_survey'
          AND nullif(btrim(e.properties->>'answer'), '') IS NOT NULL
        GROUP BY 1
        ORDER BY count DESC, answer NULLS LAST
        LIMIT :limit
        """,
        parameters,
    )
    survey_total = (
        await db.execute(
            text(
                f"""
                SELECT count(*) AS answers
                FROM analytics_events e
                WHERE {_SCOPE}
                  AND e.name = 'onboarding.abandon_survey'
                  AND nullif(btrim(e.properties->>'answer'), '') IS NOT NULL
                """
            ),
            parameters,
        )
    ).mappings().one()

    return {
        "stage": stage,
        "window_days": days,
        "route_keys": list(routes),
        "validation_failures": [dict(row) for row in validation],
        "network_failures": [dict(row) for row in network],
        "dead_clicks": [dict(row) for row in dead_clicks],
        "rage_clicks": [dict(row) for row in rage_clicks],
        "survey": [dict(row) for row in survey],
        "survey_total": int(survey_total["answers"] or 0),
        "dwell": {
            "median_ms": float(dwell["median_ms"]) if dwell["median_ms"] is not None else None,
            "p90_ms": float(dwell["p90_ms"]) if dwell["p90_ms"] is not None else None,
            "samples": int(dwell["samples"] or 0),
        },
        "sample_events": int(samples["events"] or 0),
        "sample_sessions": int(samples["sessions"] or 0),
    }


async def build_stage_sessions(
    db: AsyncSession, *, stage: str, days: int = 30, limit: int = 50
) -> dict[str, Any]:
    """Sessions that stopped on a stage's routes and never moved past it.

    "Stopped" is deliberately simple and conservative: the last route the session
    touched belongs to the stage, and no server milestone that proves progress
    beyond the stage was recorded on the company (or the person, before there is
    a company) after the session was last seen.
    """
    routes = stage_routes(stage)
    later = later_milestones(stage)
    rows = await _rows(
        db,
        """
        WITH last_route AS (
            SELECT DISTINCT ON (e.session_id)
                   e.session_id,
                   e.route_key
            FROM analytics_events e
            WHERE e.session_id IS NOT NULL
              AND e.occurred_at >= :since
              AND e.route_key IS NOT NULL
            ORDER BY e.session_id, e.occurred_at DESC, e.id DESC
        ),
        event_counts AS (
            SELECT e.session_id, count(*) AS events
            FROM analytics_events e
            WHERE e.session_id IS NOT NULL
              AND e.occurred_at >= :since
            GROUP BY e.session_id
        )
        SELECT s.id,
               s.user_id,
               s.company_id,
               s.started_at,
               s.last_seen_at,
               s.exit_route,
               s.device_type,
               s.browser,
               s.locale,
               s.source,
               coalesce(ec.events, 0) AS events,
               lr.route_key AS last_route_key
        FROM analytics_sessions s
        JOIN last_route lr ON lr.session_id = s.id
        LEFT JOIN event_counts ec ON ec.session_id = s.id
        WHERE s.last_seen_at >= :since
          AND s.is_internal = false
          AND lr.route_key = ANY(CAST(:routes AS text[]))
          AND NOT EXISTS (
              SELECT 1 FROM users u
              WHERE u.id = s.user_id AND u.platform_role IS NOT NULL
          )
          AND NOT EXISTS (
              SELECT 1 FROM analytics_events m
              WHERE m.name = ANY(CAST(:later AS text[]))
                AND m.occurred_at > s.last_seen_at
                AND (
                    m.company_id = s.company_id
                    OR m.user_id = s.user_id
                )
          )
        ORDER BY s.last_seen_at DESC, s.id
        LIMIT :limit
        """,
        {
            "since": _window(days),
            "routes": list(routes),
            "later": list(later),
            "limit": limit,
        },
    )
    return {
        "stage": stage,
        "window_days": days,
        "route_keys": list(routes),
        "limit": limit,
        "sessions": [dict(row) for row in rows],
    }


async def build_session_timeline(db: AsyncSession, *, session_id: UUID) -> dict[str, Any] | None:
    """One session and its events in time order, or ``None`` when not visible.

    Internal sessions return ``None`` as well: platform staff testing the product
    must not become a browsable timeline just because an admin opened the page.
    """
    session = (
        await db.execute(
            text(
                """
                SELECT id, user_id, company_id, started_at, last_seen_at,
                       exit_route, device_type, browser, locale, source, is_internal
                FROM analytics_sessions
                WHERE id = :session_id
                """
            ),
            {"session_id": session_id},
        )
    ).mappings().one_or_none()
    if session is None or session["is_internal"]:
        return None
    rows = await _rows(
        db,
        """
        SELECT e.occurred_at,
               e.name,
               e.route_key,
               e.element_key,
               e.duration_ms,
               e.properties
        FROM analytics_events e
        WHERE e.session_id = :session_id
          AND NOT EXISTS (
              SELECT 1 FROM users u
              WHERE u.id = e.user_id AND u.platform_role IS NOT NULL
          )
        ORDER BY e.occurred_at ASC, e.id ASC
        LIMIT :limit
        """,
        {"session_id": session_id, "limit": _TIMELINE_LIMIT + 1},
    )
    truncated = len(rows) > _TIMELINE_LIMIT
    events = [dict(row) for row in rows[:_TIMELINE_LIMIT]]
    return {
        "id": session["id"],
        "user_id": session["user_id"],
        "company_id": session["company_id"],
        "started_at": session["started_at"],
        "last_seen_at": session["last_seen_at"],
        "exit_route": session["exit_route"],
        "device_type": session["device_type"],
        "browser": session["browser"],
        "locale": session["locale"],
        "source": session["source"],
        "truncated": truncated,
        "events": events,
    }
