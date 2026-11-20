"""First-party product telemetry: capture, sanitise, emit and roll up.

Design rules, in order of importance:

1. **Never break the product.** ``emit()`` swallows its own errors, and the
   collector endpoint returns a result even when a row cannot be stored. A sale
   must not fail because analytics did.
2. **Server milestones are authoritative.** The browser can be closed, blocked
   or offline exactly when a merchant gives up, so the funnel counts
   ``source='api'`` rows. Client rows explain behaviour; they never define a
   conversion.
3. **Content, not coverage, is limited.** We record which control was clicked and
   on which route, never what was typed. Credentials, tokens, payment links and
   personal details are stripped before storage.
4. **Time is the partition key.** Raw events live for a bounded window and are
   dropped by partition, not by a mass delete; rollups outlive them.

See ``docs/onboarding-activation-analytics-plan.md`` and
``docs/activation-intelligence-requirements.md``.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics_registry import client_event, server_event
from app.config import settings
from app.models import (
    AnalyticsEvent,
    AnalyticsSession,
    Membership,
    MembershipStore,
    Store,
    User,
    utcnow,
)
from app.security import decode_token
from app.services.sessions import get_active_session

logger = logging.getLogger("chmaba.analytics")

# Keys whose values are never useful for product analysis and are always
# stripped, at any depth. Substring rules cover the variants a hurried client
# might send (access_token, authToken, card_number, ...).
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "passcode",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "authorization",
        "api_key",
        "secret",
        "card",
        "card_number",
        "cvv",
        "cvc",
        "pin",
        "otp",
        "verification_id",
        "verification_token",
        "qr_string",
        "qr_code",
        "aba_payway_link",
        "payment_link",
        "phone",
        "email",
        "full_name",
        "address",
        "code",
    }
)
_SENSITIVE_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "api_key",
    "card",
    "cvv",
    "cvc",
    "otp",
    "phone",
    "email",
)

_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_LONG_HEX_RE = re.compile(r"\b[0-9a-fA-F]{16,}\b")
_BOT_MARKERS = ("bot", "crawler", "spider", "headless", "phantomjs", "lighthouse")

_MAX_STRING = 200
_MAX_LIST = 20
_MAX_DEPTH = 3


def enabled() -> bool:
    return bool(settings.analytics_enabled)


def internal_domains() -> set[str]:
    return {
        domain.strip().lower()
        for domain in (settings.analytics_internal_email_domains or "").split(",")
        if domain.strip()
    }


def looks_like_bot(user_agent: str | None) -> bool:
    """Cheap crawler filter. Turnstile already guards sign-up; this keeps the
    event table clean of link-preview fetchers and monitors."""
    if not user_agent:
        return True
    lowered = user_agent.lower()
    return any(marker in lowered for marker in _BOT_MARKERS)


def is_internal(user: User | None) -> bool:
    if user is None:
        return False
    if user.platform_role:
        return True
    domain = (user.email or "").rsplit("@", 1)[-1].lower()
    return domain in internal_domains()


def hash_ip(ip: str | None) -> str | None:
    """A deployment-scoped hash. The raw address is never stored."""
    if not ip:
        return None
    return hashlib.sha256(f"{settings.analytics_ip_salt}:{ip}".encode("utf-8")).hexdigest()


def normalize_route(value: str | None) -> str | None:
    """Keep a path, drop its query, fragment and any id-shaped segment.

    Verification and reset links carry ``?token=``; the URL is the most likely
    place a secret would leak into analytics. Query and fragment are removed
    before anything else.
    """
    if not value:
        return None
    path = value.split("#", 1)[0].split("?", 1)[0].strip()
    if not path:
        return None
    path = _UUID_RE.sub(":id", path)
    path = _LONG_HEX_RE.sub(":token", path)
    return path[:200]


def _sensitive(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    if normalized in _SENSITIVE_KEYS:
        return True
    return any(fragment in normalized for fragment in _SENSITIVE_FRAGMENTS)


def sanitize_properties(value: Any, *, depth: int = 0) -> Any:
    """Strip secrets and cap shape. Unknown types become strings."""
    if depth > _MAX_DEPTH:
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:_MAX_STRING]
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or _sensitive(key):
                continue
            cleaned[key[:80]] = sanitize_properties(item, depth=depth + 1)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [sanitize_properties(item, depth=depth + 1) for item in value[:_MAX_LIST]]
    return str(value)[:_MAX_STRING]


def sanitize_event_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    """Sanitise and enforce the per-event byte budget."""
    cleaned = sanitize_properties(properties or {})
    if not isinstance(cleaned, dict):
        return {}
    encoded = json.dumps(cleaned, ensure_ascii=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) <= settings.analytics_max_event_bytes:
        return cleaned
    # Too large: keep the small scalars only, then give up and store nothing.
    reduced = {
        key: value
        for key, value in cleaned.items()
        if isinstance(value, (bool, int, float)) or (isinstance(value, str) and len(value) <= 80)
    }
    if len(json.dumps(reduced).encode("utf-8")) <= settings.analytics_max_event_bytes:
        return reduced
    return {}


async def optional_user(db: AsyncSession, token: str | None) -> User | None:
    """Resolve a bearer token without ever raising.

    A stale token on a telemetry batch must not turn into a 401: the client
    would retry, lose events, and possibly surface an error over a sale screen.
    """
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user_id = UUID(payload["sub"])
        session_id = UUID(payload["sid"])
        session = await get_active_session(db, session_id)
        if session is None or session.user_id != user_id:
            return None
        return await db.get(User, user_id)
    except Exception:
        return None


async def identity_for(db: AsyncSession, user: User | None) -> tuple[UUID | None, UUID | None]:
    """Server-derived company/store. Client-supplied ids are never trusted."""
    if user is None:
        return None, None
    membership = (
        await db.execute(
            select(Membership)
            .where(Membership.user_id == user.id, Membership.status == "active")
            .order_by(Membership.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if membership is None:
        return None, None
    store_id = await db.scalar(
        select(MembershipStore.store_id)
        .where(MembershipStore.membership_id == membership.id)
        .order_by(MembershipStore.store_id)
        .limit(1)
    )
    if store_id is None:
        store_id = await db.scalar(
            select(Store.id).where(Store.company_id == membership.company_id).order_by(Store.created_at).limit(1)
        )
    return membership.company_id, store_id


def _clamp_time(value: datetime | None) -> datetime:
    now = utcnow()
    if value is None:
        return now
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return min(max(value, now - timedelta(days=30)), now + timedelta(days=7))


async def upsert_session(
    db: AsyncSession,
    *,
    session_id: UUID,
    anonymous_id: UUID,
    source: str,
    started_at: datetime | None,
    entry_route: str | None,
    exit_route: str | None = None,
    referrer_host: str | None = None,
    utm: dict[str, str] | None = None,
    app_version: str | None = None,
    platform: str | None = None,
    os_name: str | None = None,
    browser: str | None = None,
    device_type: str | None = None,
    locale: str | None = None,
    timezone_name: str | None = None,
    user: User | None = None,
    ip_hash: str | None = None,
    user_agent: str | None = None,
) -> None:
    company_id, store_id = await identity_for(db, user)
    utm_values = {key: (utm or {}).get(key) for key in ("source", "medium", "campaign", "content", "term")}
    values = {
        "id": session_id,
        "anonymous_id": anonymous_id,
        "user_id": user.id if user else None,
        "company_id": company_id,
        "store_id": store_id,
        "source": source,
        "started_at": _clamp_time(started_at),
        "last_seen_at": utcnow(),
        "entry_route": normalize_route(entry_route),
        "exit_route": normalize_route(exit_route),
        "referrer_host": (referrer_host or None) and referrer_host[:200],
        "utm_source": utm_values["source"],
        "utm_medium": utm_values["medium"],
        "utm_campaign": utm_values["campaign"],
        "utm_content": utm_values["content"],
        "utm_term": utm_values["term"],
        "app_version": app_version,
        "platform": platform,
        "os": os_name,
        "browser": browser,
        "device_type": device_type,
        "locale": locale,
        "timezone": timezone_name,
        "is_internal": is_internal(user),
        "ip_hash": ip_hash,
        "user_agent": (user_agent or None) and user_agent[:400],
    }
    statement = pg_insert(AnalyticsSession).values(**values)
    statement = statement.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "last_seen_at": statement.excluded.last_seen_at,
            "user_id": func.coalesce(statement.excluded.user_id, AnalyticsSession.user_id),
            "company_id": func.coalesce(statement.excluded.company_id, AnalyticsSession.company_id),
            "store_id": func.coalesce(statement.excluded.store_id, AnalyticsSession.store_id),
            "exit_route": func.coalesce(statement.excluded.exit_route, AnalyticsSession.exit_route),
            "is_internal": or_(AnalyticsSession.is_internal, statement.excluded.is_internal),
            "ended_at": None,
        },
    )
    await db.execute(statement)


async def record_batch(
    db: AsyncSession,
    *,
    source: str,
    session_id: UUID,
    anonymous_id: UUID,
    events: list[dict[str, Any]],
    user: User | None,
    app_version: str | None = None,
    platform: str | None = None,
    os_name: str | None = None,
    browser: str | None = None,
    device_type: str | None = None,
    locale: str | None = None,
    timezone_name: str | None = None,
) -> tuple[int, int]:
    """Store accepted events, return ``(accepted, dropped)``.

    Unknown names, unregistered properties and repeats of the same ``event_id``
    are dropped rather than stored. Dropping is counted so the health page can
    show a client drifting from the registry.
    """
    company_id, store_id = await identity_for(db, user)
    context = {
        "app_version": app_version,
        "platform": platform,
        "os": os_name,
        "browser": browser,
        "device_type": device_type,
        "locale": locale,
        "timezone": timezone_name,
    }
    rows: list[dict[str, Any]] = []
    dropped = 0
    seen: set[UUID] = set()
    for event in events:
        name = str(event.get("name") or "")
        spec = client_event(name)
        if spec is None:
            dropped += 1
            continue
        event_id = event.get("id")
        if not isinstance(event_id, UUID) or event_id in seen:
            dropped += 1
            continue
        seen.add(event_id)
        rows.append(
            {
                "occurred_at": _clamp_time(event.get("occurred_at")),
                "event_id": event_id,
                "session_id": session_id,
                "anonymous_id": anonymous_id,
                "user_id": user.id if user else None,
                "company_id": company_id,
                "store_id": store_id,
                "name": name,
                "version": spec.version,
                "source": source,
                "route": normalize_route(event.get("route")),
                "route_key": (event.get("route_key") or None) and str(event["route_key"])[:80],
                "element_key": (event.get("element_key") or None) and str(event["element_key"])[:120],
                "duration_ms": event.get("duration_ms"),
                "properties": sanitize_event_properties(event.get("props")),
                "context": context,
            }
        )
    if not rows:
        return 0, dropped
    statement = pg_insert(AnalyticsEvent).values(rows)
    # The client retries on reconnect, so the same id can arrive twice; the
    # unique (event_id, occurred_at) pair makes the repeat a no-op.
    statement = statement.on_conflict_do_nothing(index_elements=["event_id", "occurred_at"])
    result = await db.execute(statement)
    stored = result.rowcount if result.rowcount is not None and result.rowcount >= 0 else len(rows)
    return stored, dropped + max(len(rows) - stored, 0)


def emit(
    db: AsyncSession,
    name: str,
    *,
    user: User | None = None,
    company_id: UUID | None = None,
    store_id: UUID | None = None,
    session_id: UUID | None = None,
    anonymous_id: UUID | None = None,
    properties: dict[str, Any] | None = None,
) -> None:
    """Add one authoritative milestone to the caller's transaction.

    Deliberately synchronous and non-raising: it is called from the same
    function that commits the business row, so the milestone and the row survive
    or roll back together. A registered name is required; an unknown one is
    logged and ignored rather than breaking a sign-up or a sale.
    """
    if not enabled():
        return
    try:
        spec = server_event(name)
        if spec is None:
            logger.warning("analytics: unknown server event %r ignored", name)
            return
        db.add(
            AnalyticsEvent(
                occurred_at=utcnow(),
                event_id=uuid.uuid4(),
                session_id=session_id,
                anonymous_id=anonymous_id,
                user_id=user.id if user else None,
                company_id=company_id,
                store_id=store_id,
                name=name,
                version=spec.version,
                source="api",
                properties=sanitize_event_properties(properties),
                context={"authoritative": True},
            )
        )
    except Exception:  # analytics must never break a signup, sale or refund
        logger.exception("analytics: could not emit %r", name)


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return value.replace(year=year, month=month, day=1)


async def ensure_partitions(db: AsyncSession, *, months_back: int = 1, months_ahead: int = 3) -> list[str]:
    """Create the monthly partitions the collector needs, idempotently.

    A missing partition is the one failure mode that would silently lose events,
    so the worker runs this hourly and always creates a few months ahead.
    """
    start = _month_start(utcnow())
    created: list[str] = []
    for offset in range(-months_back, months_ahead + 1):
        lower = _add_months(start, offset)
        upper = _add_months(lower, 1)
        name = f"analytics_events_{lower.strftime('%Y_%m')}"
        await db.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF analytics_events "
                f"FOR VALUES FROM ('{lower.isoformat()}') TO ('{upper.isoformat()}')"
            )
        )
        created.append(name)
    return created


async def rebuild_rollups(db: AsyncSession, *, days: int = 3) -> int:
    """Recompute the last ``days`` of daily aggregates from raw events."""
    since = utcnow() - timedelta(days=days)
    await db.execute(text("DELETE FROM analytics_daily_rollups WHERE day >= :since"), {"since": since.date()})
    result = await db.execute(
        text(
            """
            INSERT INTO analytics_daily_rollups
                (day, name, route_key, source, company_key, events, sessions, users, p50_ms, p95_ms)
            SELECT
                date_trunc('day', occurred_at)::date AS day,
                name,
                coalesce(route_key, '') AS route_key,
                coalesce(source, '') AS source,
                coalesce(company_id::text, '') AS company_key,
                count(*) AS events,
                count(DISTINCT session_id) AS sessions,
                count(DISTINCT user_id) AS users,
                (percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms))::int AS p50_ms,
                (percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms))::int AS p95_ms
            FROM analytics_events
            WHERE occurred_at >= :since
            GROUP BY 1, 2, 3, 4, 5
            ON CONFLICT (day, name, route_key, source, company_key) DO UPDATE SET
                events = excluded.events,
                sessions = excluded.sessions,
                users = excluded.users,
                p50_ms = excluded.p50_ms,
                p95_ms = excluded.p95_ms
            """
        ),
        {"since": since},
    )
    return result.rowcount or 0


async def purge_expired(db: AsyncSession) -> dict[str, int]:
    """Drop raw partitions past retention and old rollups."""
    partitions = (
        await db.execute(
            text(
                """
                SELECT child.relname
                FROM pg_inherits
                JOIN pg_class parent ON parent.oid = pg_inherits.inhparent
                JOIN pg_class child ON child.oid = pg_inherits.inhrelid
                WHERE parent.relname = 'analytics_events'
                  AND child.relname LIKE 'analytics_events_%'
                """
            )
        )
    ).scalars().all()
    raw_cutoff = utcnow() - timedelta(days=settings.analytics_raw_retention_days)
    dropped = 0
    for name in partitions:
        suffix = name.removeprefix("analytics_events_")
        try:
            year, month = (int(part) for part in suffix.split("_")[:2])
            month_end = _add_months(datetime(year, month, 1, tzinfo=timezone.utc), 1)
        except (ValueError, TypeError):
            continue
        if month_end < raw_cutoff:
            await db.execute(text(f"DROP TABLE IF EXISTS {name}"))
            dropped += 1
    rollup_cutoff = (utcnow() - timedelta(days=settings.analytics_rollup_retention_days)).date()
    rollups = await db.execute(
        text("DELETE FROM analytics_daily_rollups WHERE day < :cutoff"), {"cutoff": rollup_cutoff}
    )
    return {"partitions_dropped": dropped, "rollups_deleted": rollups.rowcount or 0}


async def run_maintenance(db: AsyncSession) -> dict[str, Any]:
    """The hourly job: create partitions, refresh rollups, retire old data."""
    partitions = await ensure_partitions(db)
    rows = await rebuild_rollups(db, days=3)
    purged = await purge_expired(db)
    return {"partitions": len(partitions), "rollup_rows": rows, **purged}
