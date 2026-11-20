"""Cohort activation funnel: one signup cohort, authoritative milestones.

The existing ``/admin/funnel`` counts each stage independently over the same
window, so "conversion from previous" mixes denominators. This module fixes
that: it takes the companies created in the window (with their owner), then asks
how many of *that cohort* reached each later stage.

Stage counts are monotonic by construction. A merchant who created a workspace
necessarily verified, signed in and opened setup, even if the explanatory event
was lost (an older client, a blocked request). Where a timestamp is missing we
carry the later one forward, which makes the timing conservative rather than
optimistic.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import internal_domains

_STAGES: tuple[tuple[str, str, bool], ...] = (
    ("account_created", "Account created", True),
    ("email_verified", "Email verified", True),
    ("first_login", "First sign-in", True),
    ("setup_opened", "Setup opened", False),
    ("workspace_created", "Workspace created", True),
    ("first_product", "Added first product", True),
    ("shift_opened", "Opened a shift", True),
    ("first_sale", "Made first sale", True),
    ("second_sale", "Made a second sale", True),
)

_SQL = """
WITH cohort AS (
    SELECT co.id AS company_id,
           co.created_at AS workspace_at,
           m.user_id,
           u.created_at AS signup_at,
           u.is_email_verified,
           u.email
    FROM companies co
    JOIN memberships m ON m.company_id = co.id AND m.role = 'owner' AND m.status = 'active'
    JOIN users u ON u.id = m.user_id
    WHERE co.created_at >= :since
),
user_events AS (
    SELECT e.user_id,
           min(e.occurred_at) FILTER (WHERE e.name = 'user.email_verified') AS verified_at,
           min(e.occurred_at) FILTER (WHERE e.name = 'user.logged_in') AS login_at,
           min(e.occurred_at) FILTER (WHERE e.name = 'onboarding.step_viewed') AS setup_at
    FROM analytics_events e
    JOIN cohort c ON c.user_id = e.user_id
    GROUP BY e.user_id
),
company_events AS (
    SELECT e.company_id,
           min(e.occurred_at) FILTER (WHERE e.name = 'product.created') AS product_at,
           min(e.occurred_at) FILTER (WHERE e.name = 'shift.opened') AS shift_at
    FROM analytics_events e
    JOIN cohort c ON c.company_id = e.company_id
    GROUP BY e.company_id
),
sales AS (
    SELECT c.company_id,
           min(o.created_at) FILTER (WHERE o.status = 'paid') AS first_sale_at,
           count(o.id) FILTER (WHERE o.status = 'paid') AS paid_orders
    FROM cohort c
    LEFT JOIN stores s ON s.company_id = c.company_id
    LEFT JOIN orders o ON o.store_id = s.id
    GROUP BY c.company_id
)
SELECT c.company_id, c.user_id, c.signup_at, c.workspace_at, c.is_email_verified, c.email,
       ue.verified_at, ue.login_at, ue.setup_at,
       ce.product_at, ce.shift_at,
       s.first_sale_at, coalesce(s.paid_orders, 0) AS paid_orders
FROM cohort c
LEFT JOIN user_events ue ON ue.user_id = c.user_id
LEFT JOIN company_events ce ON ce.company_id = c.company_id
LEFT JOIN sales s ON s.company_id = c.company_id
"""


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(int(quantile * (len(ordered) - 1)), len(ordered) - 1)
    return round(ordered[index], 2)


def _seconds_between(start: datetime, end: datetime) -> float:
    delta = (end - start).total_seconds()
    return round(max(delta, 0.0), 2)


def _row_timestamps(row: Any) -> dict[str, datetime | None]:
    """First time the owner reached each stage, made monotonic.

    A later stage implies every earlier one. Carrying its timestamp backwards is
    the honest reading: we know the merchant got past the earlier screen, even
    when the explanatory event never arrived.
    """
    workspace_at = row["workspace_at"]
    first_sale_at = row["first_sale_at"]
    verified = row["verified_at"] or (row["signup_at"] if row["is_email_verified"] else None) or workspace_at
    login = row["login_at"] or workspace_at
    setup = row["setup_at"] or workspace_at
    product = row["product_at"] or first_sale_at
    shift = row["shift_at"] or first_sale_at
    second = first_sale_at if (row["paid_orders"] or 0) >= 2 else None
    return {
        "account_created": row["signup_at"],
        "email_verified": verified,
        "first_login": login,
        "setup_opened": setup,
        "workspace_created": workspace_at,
        "first_product": product,
        "shift_opened": shift,
        "first_sale": first_sale_at,
        "second_sale": second,
    }


async def build_funnel(db: AsyncSession, *, days: int = 30) -> dict[str, Any]:
    """Cohort funnel for companies created in the last ``days`` days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await db.execute(text(_SQL), {"since": since})).mappings().all()

    excluded = internal_domains()
    cohort = [
        row
        for row in rows
        if not (row["email"] or "").rsplit("@", 1)[-1].lower() in excluded
    ]

    totals: dict[str, int] = {key: 0 for key, _, _ in _STAGES}
    durations: dict[str, list[float]] = {key: [] for key, _, _ in _STAGES}
    for row in cohort:
        signup_at = row["signup_at"]
        for key, timestamp in _row_timestamps(row).items():
            if timestamp is None:
                continue
            totals[key] += 1
            durations[key].append(_seconds_between(signup_at, timestamp))

    total = len(cohort)
    stages: list[dict[str, Any]] = []
    previous: int | None = None
    for key, label, authoritative in _STAGES:
        count = totals[key]
        stages.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "authoritative": authoritative,
                "from_previous": (count / previous) if previous else None,
                "from_start": (count / total) if total else None,
                "median_seconds": _percentile(durations[key], 0.5),
                "p90_seconds": _percentile(durations[key], 0.9),
                "stalled": max(total - count, 0),
            }
        )
        previous = count

    return {
        "window_days": days,
        "cohort": "companies",
        "total": total,
        "stages": stages,
    }


async def build_health(db: AsyncSession, *, hours: int = 24) -> dict[str, Any]:
    """Ingest health for the telemetry pipeline.

    A funnel nobody can trust is worse than no funnel, so the admin page shows
    volume, the age of the newest event, and how many partitions exist. Rejected
    events are not stored (by design); the collector's response is the signal
    for a client drifting from the registry.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    row = (
        await db.execute(
            text(
                """
                SELECT count(*) AS events,
                       count(DISTINCT session_id) AS sessions,
                       count(DISTINCT user_id) AS users,
                       max(received_at) AS last_event_at
                FROM analytics_events
                WHERE occurred_at >= :since
                """
            ),
            {"since": since},
        )
    ).mappings().one()
    partitions = await db.scalar(
        text(
            "SELECT count(*) FROM pg_inherits "
            "JOIN pg_class parent ON parent.oid = pg_inherits.inhparent "
            "WHERE parent.relname = 'analytics_events'"
        )
    )
    last_event_at = row["last_event_at"]
    lag = (datetime.now(timezone.utc) - last_event_at).total_seconds() if last_event_at else None
    return {
        "window_hours": hours,
        "events": int(row["events"] or 0),
        "sessions": int(row["sessions"] or 0),
        "users": int(row["users"] or 0),
        "last_event_at": last_event_at.isoformat() if last_event_at else None,
        "lag_seconds": round(max(lag, 0.0), 1) if lag is not None else None,
        "partitions": int(partitions or 0),
    }
