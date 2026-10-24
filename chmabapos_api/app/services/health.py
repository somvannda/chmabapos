"""Platform self-monitoring: probe every dependency, page when one breaks.

The product's own ``/health`` endpoint only answers for the database, so a
broken payment provider, a dead storefront or a mailbox that refuses mail all
looked identical to a quiet afternoon. This module sweeps the dependencies that
actually have to work for a merchant to sell - database, KHQR checkout, outbound
mail, media storage and the customer-facing hosts - records the result, and
pages the internal operations chat when one of them stays down.

Two design choices matter:

* A sweep rewrites one row per check (``system_health_checks``) and appends an
  event only when the state *changes*. The admin page and the alerting rule ask
  "is this healthy now, and since when", which a heartbeat table answers badly.
* KHQR is judged from both sides. Probing ChmabaPay only proves the provider is
  up; the failures that hurt are the ones the API itself saw while a cashier was
  trying to take money, so ``record_khqr_failure`` feeds those into the same
  check.
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Company, Store, SystemHealthCheck, SystemHealthEvent, utcnow
from app.services.mail import load_mail_settings, resolve_provider
from app.services.payments.base import PaymentProviderError
from app.services.payments.chamabapay import ChmabaPayClient
from app.services.platform_config import load_payment_settings
from app.telegram import send_telegram_message

logger = logging.getLogger(__name__)

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_DOWN = "down"
STATUS_SKIPPED = "skipped"
STATUS_UNKNOWN = "unknown"

UNHEALTHY_STATUSES = frozenset({STATUS_DEGRADED, STATUS_DOWN})
STATUS_ORDER = {STATUS_DOWN: 0, STATUS_DEGRADED: 1, STATUS_UNKNOWN: 2, STATUS_OK: 3, STATUS_SKIPPED: 4}
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

RESEND_DOMAINS_ENDPOINT = "https://api.resend.com/domains"
TELEGRAM_API_BASE = "https://api.telegram.org"

# Recent KHQR attempts, kept in memory. The point is to notice a burst within
# the current process ("cashiers are failing right now"), not to keep an audit
# trail - the provider error is already logged and the order never commits.
_KHQR_FAILURE_WINDOW: deque[tuple[datetime, str]] = deque(maxlen=100)
_KHQR_SUCCESSES: deque[datetime] = deque(maxlen=200)


@dataclass(frozen=True)
class CheckResult:
    """What one probe concluded."""

    status: str
    summary: str
    detail: str | None = None
    latency_ms: int | None = None


@dataclass(frozen=True)
class Check:
    """A named probe and the rules that decide how loudly it may shout.

    ``severity`` controls paging only: a ``critical`` check that degrades pages,
    a ``warning`` one has to be fully down, and ``info`` never pages. Every state
    is still visible on the admin page.
    """

    name: str
    label: str
    category: str
    severity: str
    probe: Callable[[AsyncSession], Awaitable[CheckResult]]


def record_khqr_success() -> None:
    """Note that a KHQR code was minted, clearing a failure streak."""
    _KHQR_SUCCESSES.append(utcnow())


def record_khqr_failure(reason: str) -> None:
    """Note that ChmabaPay refused or could not serve a KHQR request.

    Called from the checkout path right before the 502 goes back to the cashier.
    Cheap on purpose: it must never be the reason a sale fails differently.
    """
    _KHQR_FAILURE_WINDOW.append((utcnow(), (reason or "ChmabaPay request failed")[:400]))


def reset_khqr_signals() -> None:
    """Clear the in-memory signal (tests only)."""
    _KHQR_FAILURE_WINDOW.clear()
    _KHQR_SUCCESSES.clear()


def _recent_khqr_failures() -> list[str]:
    cutoff = utcnow() - timedelta(minutes=max(1, settings.health_check_khqr_failure_window_minutes))
    while _KHQR_FAILURE_WINDOW and _KHQR_FAILURE_WINDOW[0][0] < cutoff:
        _KHQR_FAILURE_WINDOW.popleft()
    return [reason for _, reason in _KHQR_FAILURE_WINDOW]


def _link_entries(obj: Company | Store) -> dict[str, dict]:
    """Every ABA PayWay link on a store or company, keyed by currency.

    Mirrors ``_aba_links_for`` in the checkout module: the JSON map is the source
    of truth and the legacy USD columns still answer when a record predates it.
    Kept in step deliberately - a check that read the map differently from the
    checkout path could report green while a sale is refused.
    """
    links = {
        str(currency).upper(): dict(entry)
        for currency, entry in (getattr(obj, "aba_payway_links", None) or {}).items()
        if isinstance(entry, dict)
    }
    legacy = getattr(obj, "aba_payway_link", None)
    if legacy and "USD" not in links:
        links["USD"] = {"link": legacy, "status": getattr(obj, "aba_payway_status", "none") or "none"}
    return links


def _link_tally(objects: list[Company | Store]) -> dict:
    """Count active / broken links and name the merchants that need a hand."""
    tally = {"active": 0, "error": 0, "pending": 0, "none": 0, "configured": 0, "objects": 0, "problems": []}
    for obj in objects:
        links = _link_entries(obj)
        if not links:
            continue
        tally["objects"] += 1
        for currency, entry in links.items():
            status = (entry.get("status") or "none").lower()
            has_link = bool(entry.get("link"))
            if not has_link:
                tally["none"] += 1
                continue
            tally["configured"] += 1
            if status == "active":
                tally["active"] += 1
            elif status == "error":
                tally["error"] += 1
                tally["problems"].append(f"{getattr(obj, 'name', None) or obj.id} ({currency})")
            else:
                # "pending" and anything unrecognised: a link exists but the
                # provider has not confirmed it, so it cannot mint a QR yet.
                tally["pending"] += 1
    return tally


async def _platform_links(db: AsyncSession) -> dict:
    stores = (await db.execute(select(Store))).scalars().all()
    companies = (await db.execute(select(Company))).scalars().all()
    tally = _link_tally(list(stores) + list(companies))
    tally["merchants"] = len(stores) + len(companies)
    return tally


async def _probe_database(db: AsyncSession) -> CheckResult:
    started = time.perf_counter()
    await db.execute(select(1))
    latency = int((time.perf_counter() - started) * 1000)
    if latency > settings.health_check_slow_query_ms:
        return CheckResult(
            STATUS_DEGRADED,
            f"Responding slowly ({latency} ms)",
            f"A trivial query took {latency} ms, above the {settings.health_check_slow_query_ms} ms threshold.",
            latency,
        )
    return CheckResult(STATUS_OK, f"Responding in {latency} ms", None, latency)


async def _probe_khqr_generation(db: AsyncSession) -> CheckResult:
    """Can a cashier mint a QR and take money right now?

    Four things have to hold at once: live mode, an API key, a reachable and
    authenticating provider, and at least one merchant with an active link. A
    provider that answers but has no active merchant link still means "KHQR is
    down", which is exactly the state that used to go unnoticed.
    """
    cfg = await load_payment_settings(db)
    mode = (cfg.get("chamabapay_mode") or "mock").strip().lower()
    if mode != "live":
        return CheckResult(
            STATUS_SKIPPED,
            "ChmabaPay is in mock mode",
            "Real QR payments are disabled (CHAMABAPAY_MODE=mock). Switch the provider to live in Admin -> Settings -> Payments to take KHQR.",
        )
    api_key = (cfg.get("chamabapay_api_key") or "").strip()
    if not api_key:
        return CheckResult(
            STATUS_DOWN,
            "ChmabaPay API key is missing",
            "Live mode cannot mint a KHQR without an API key. Add one in Admin -> Settings -> Payments.",
        )

    started = time.perf_counter()
    client = ChmabaPayClient(
        mode="live",
        api_url=(cfg.get("chamabapay_api_url") or "").strip() or None,
        api_key=api_key,
    )
    try:
        stores = await client.list_stores()
    except PaymentProviderError as exc:
        return CheckResult(STATUS_DOWN, f"Cannot reach ChmabaPay: {exc}", "Every KHQR checkout will fail until the provider answers again.")
    latency = int((time.perf_counter() - started) * 1000)

    links = await _platform_links(db)
    if links["active"] == 0:
        if links["configured"] == 0:
            return CheckResult(
                STATUS_SKIPPED,
                "No merchant has connected an ABA PayWay link yet",
                "ChmabaPay is reachable; nobody can mint a KHQR until a store or company saves a link.",
                latency,
            )
        return CheckResult(
            STATUS_DOWN,
            "No merchant has an active KHQR link",
            "ChmabaPay is reachable but nobody can be paid: every store and company link is pending or in error.",
            latency,
        )

    failures = _recent_khqr_failures()
    window = settings.health_check_khqr_failure_window_minutes
    if len(failures) >= 2:
        return CheckResult(
            STATUS_DOWN,
            f"{len(failures)} KHQR requests failed in the last {window} minutes",
            f"Latest error: {failures[-1]}",
            latency,
        )
    if failures:
        return CheckResult(
            STATUS_DEGRADED,
            f"1 KHQR request failed in the last {window} minutes",
            f"Latest error: {failures[-1]}",
            latency,
        )
    return CheckResult(
        STATUS_OK,
        f"Minting for {links['active']} merchant link(s) at {len(stores)} ChmabaPay store(s)",
        None,
        latency,
    )


async def _probe_khqr_links(db: AsyncSession) -> CheckResult:
    links = await _platform_links(db)
    if links["objects"] == 0:
        return CheckResult(STATUS_SKIPPED, "No merchant has connected an ABA PayWay link yet")
    if links["error"]:
        return CheckResult(
            STATUS_DEGRADED,
            f"{links['error']} merchant link(s) failed verification",
            "Needs a fix in Admin -> Payment links: " + ", ".join(links["problems"][:5]),
        )
    if links["pending"]:
        # Onboarding is not an outage: a link awaiting ABA PayWay activation is
        # normal for a day and is listed on the payment-links page anyway.
        return CheckResult(
            STATUS_OK,
            f"{links['active']} merchant link(s) active, {links['pending']} awaiting activation",
        )
    return CheckResult(STATUS_OK, f"{links['active']} merchant link(s) active")


async def _probe_email(db: AsyncSession) -> CheckResult:
    """Is outbound mail deliverable, not just configured?"""
    cfg = await load_mail_settings(db)
    provider = resolve_provider(cfg)
    started = time.perf_counter()
    if provider == "resend":
        api_key = (cfg.get("resend_api_key") or "").strip()
        if not api_key:
            return CheckResult(STATUS_DOWN, "Resend is selected but no API key is configured", "Every signup, receipt and reminder email will fail.")
        try:
            async with httpx.AsyncClient(timeout=settings.health_check_timeout_seconds) as client:
                response = await client.get(RESEND_DOMAINS_ENDPOINT, headers={"Authorization": f"Bearer {api_key}"})
        except httpx.HTTPError as exc:
            return CheckResult(STATUS_DOWN, f"Cannot reach Resend: {exc.__class__.__name__}", "Outbound email is not leaving the platform.")
        latency = int((time.perf_counter() - started) * 1000)
        if response.status_code == 401:
            return CheckResult(STATUS_DOWN, "Resend rejected the API key (401)", "Rotate the key in Admin -> Settings -> Mail.", latency)
        if response.status_code >= 500:
            return CheckResult(STATUS_DOWN, f"Resend is unhealthy ({response.status_code})", None, latency)
        if response.status_code >= 400:
            return CheckResult(STATUS_DEGRADED, f"Resend answered {response.status_code}", "The key may lack the domains scope.", latency)
        return CheckResult(STATUS_OK, "Resend accepts the API key", None, latency)

    host = (settings.smtp_host or "").strip()
    if not host:
        return CheckResult(STATUS_DOWN, "No SMTP host is configured", "Outbound email is not leaving the platform.")
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, settings.smtp_port),
            timeout=settings.health_check_timeout_seconds,
        )
        writer.close()
        await asyncio.wait_for(writer.wait_closed(), timeout=2)
    except (OSError, asyncio.TimeoutError) as exc:
        return CheckResult(STATUS_DOWN, f"Cannot reach the SMTP relay ({host}:{settings.smtp_port})", f"{exc.__class__.__name__}: {exc}")
    latency = int((time.perf_counter() - started) * 1000)
    return CheckResult(STATUS_OK, f"SMTP relay reachable at {host}:{settings.smtp_port}", None, latency)


def _media_round_trip() -> None:
    root = settings.media_root
    os.makedirs(root, exist_ok=True)
    handle, path = tempfile.mkstemp(prefix=".health-", dir=root)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write("ok")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


async def _probe_media(db: AsyncSession) -> CheckResult:
    del db
    started = time.perf_counter()
    try:
        await asyncio.wait_for(asyncio.to_thread(_media_round_trip), timeout=settings.health_check_timeout_seconds)
    except (OSError, asyncio.TimeoutError) as exc:
        return CheckResult(STATUS_DOWN, "Media storage is not writable", f"{exc.__class__.__name__}: {exc}")
    latency = int((time.perf_counter() - started) * 1000)
    return CheckResult(STATUS_OK, "Product images can be written", None, latency)


async def _probe_http(label: str, url: str, *, path: str = "") -> CheckResult:
    target = f"{url.rstrip('/')}{path}"
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.health_check_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(target)
    except httpx.HTTPError as exc:
        return CheckResult(STATUS_DOWN, f"{label} is unreachable", f"{exc.__class__.__name__} requesting {target}")
    latency = int((time.perf_counter() - started) * 1000)
    if response.status_code >= 500:
        return CheckResult(STATUS_DOWN, f"{label} answered {response.status_code}", f"{target} is failing requests.", latency)
    if response.status_code >= 400:
        return CheckResult(STATUS_DEGRADED, f"{label} answered {response.status_code}", target, latency)
    return CheckResult(STATUS_OK, f"{label} responding ({response.status_code})", None, latency)


async def _probe_storefront(db: AsyncSession) -> CheckResult:
    del db
    if not (settings.storefront_url or "").strip():
        return CheckResult(STATUS_SKIPPED, "No storefront host is configured")
    return await _probe_http("Storefront", settings.storefront_url, path="/healthz")


async def _probe_pos_web(db: AsyncSession) -> CheckResult:
    del db
    if not (settings.frontend_url or "").strip():
        return CheckResult(STATUS_SKIPPED, "No web POS host is configured")
    return await _probe_http("Web POS", settings.frontend_url, path="/")


async def _probe_telegram(db: AsyncSession) -> CheckResult:
    del db
    token = (settings.telegram_bot_token or "").strip()
    if not settings.telegram_enabled or not token:
        return CheckResult(STATUS_SKIPPED, "Telegram alerts are not configured")
    try:
        async with httpx.AsyncClient(timeout=settings.health_check_timeout_seconds) as client:
            response = await client.get(f"{TELEGRAM_API_BASE}/bot{token}/getMe")
    except httpx.HTTPError as exc:
        return CheckResult(STATUS_DEGRADED, "Cannot reach the Telegram API", exc.__class__.__name__)
    if response.status_code != 200:
        return CheckResult(STATUS_DEGRADED, "Telegram rejected the bot token", f"getMe answered {response.status_code}.")
    return CheckResult(STATUS_OK, "Bot token accepted")


async def _probe_ai(db: AsyncSession) -> CheckResult:
    del db
    if not (settings.ai_provider or "").strip():
        return CheckResult(STATUS_SKIPPED, "No AI provider is configured")
    if not (settings.ai_api_key or "").strip():
        return CheckResult(STATUS_DEGRADED, "AI provider is selected but no API key is set", "AI drafting and the support assistant will fail.")
    return CheckResult(STATUS_OK, f"{settings.ai_provider} configured")


CHECKS: tuple[Check, ...] = (
    Check("database", "Database", "infrastructure", "critical", _probe_database),
    Check("khqr_generation", "KHQR checkout", "payments", "critical", _probe_khqr_generation),
    Check("khqr_links", "Merchant payment links", "payments", "warning", _probe_khqr_links),
    Check("email_outbound", "Outbound email", "delivery", "warning", _probe_email),
    Check("media_storage", "Media storage", "infrastructure", "warning", _probe_media),
    Check("storefront", "Storefront", "clients", "warning", _probe_storefront),
    Check("pos_web", "Web POS", "clients", "warning", _probe_pos_web),
    Check("telegram", "Telegram alerts", "delivery", "info", _probe_telegram),
    Check("ai_assistant", "AI assistant", "integrations", "info", _probe_ai),
)


async def _run_probe(check: Check, db: AsyncSession) -> CheckResult:
    """Run one probe, turning a crash or a hang into a result.

    A probe raising must never abort the sweep: the remaining dependencies still
    have to be checked, and "it threw" is itself a reportable state.
    """
    try:
        return await asyncio.wait_for(check.probe(db), timeout=settings.health_check_timeout_seconds)
    except asyncio.TimeoutError:
        return CheckResult(STATUS_DOWN, f"Timed out after {settings.health_check_timeout_seconds}s", "The probe did not answer in time.")
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # a broken probe is a finding, not a crash
        logger.exception("health probe %s failed", check.name)
        return CheckResult(STATUS_DOWN, f"Probe error: {exc.__class__.__name__}", str(exc)[:400])


def _needs_alert(check: Check, row: SystemHealthCheck) -> bool:
    """Which failures are worth waking the operations chat for.

    A warning that is merely degraded is visible in the admin panel but does not
    page; a critical one does. Everything still has to survive
    ``health_check_alert_after_failures`` sweeps.
    """
    if row.status == STATUS_DOWN:
        return True
    return row.status == STATUS_DEGRADED and check.severity == "critical"


def _cooldown_active(row: SystemHealthCheck, now: datetime) -> bool:
    if row.alerted_at is None:
        return False
    cooldown = timedelta(minutes=max(1, settings.health_check_alert_cooldown_minutes))
    return (now - row.alerted_at) < cooldown


def _local_time(moment: datetime) -> str:
    try:
        zone = ZoneInfo(settings.telegram_digest_timezone)
    except ZoneInfoNotFoundError:
        zone = timezone.utc
    return moment.astimezone(zone).strftime("%d %b %Y, %H:%M %Z")


def _alert_footer() -> str:
    if (settings.platform_admin_url or "").strip():
        return f"\n{(settings.platform_admin_url or '').strip().rstrip('/')}/health"
    return ""


@dataclass(frozen=True)
class _AlertItem:
    """A failure captured for the message, independent of the ORM session.

    Built before the commit on purpose: reading an expired row afterwards would
    need a lazy refresh, which async SQLAlchemy cannot do inside a formatter.
    """

    name: str
    label: str
    status: str
    summary: str
    detail: str | None


def _format_alert_message(items: list[_AlertItem], now: datetime) -> str:
    lines = ["\U0001F534 Chmaba platform alert"]
    for item in items:
        lines.append(f"\u2022 {item.label} is {item.status}: {item.summary}")
        if item.detail:
            lines.append(f"  {item.detail[:240]}")
    lines.append(f"Checked {_local_time(now)}")
    return "\n".join(lines) + _alert_footer()


def _format_recovery_message(items: list[_AlertItem], now: datetime) -> str:
    lines = ["\U0001F7E2 Chmaba recovered"]
    for item in items:
        lines.append(f"\u2022 {item.label}: {item.summary}")
    lines.append(f"Checked {_local_time(now)}")
    return "\n".join(lines) + _alert_footer()


async def run_checks(db: AsyncSession, *, trigger: str = "schedule", alert: bool = True) -> dict:
    """Run every probe, record the result and page on a sustained failure.

    ``trigger`` is ``schedule`` (the in-process worker), ``manual`` (the admin
    "Run now" button) or ``startup``. Only a scheduled sweep alerts, so an
    operator refreshing the page never triggers a page.
    """
    existing = {row.name: row for row in (await db.execute(select(SystemHealthCheck))).scalars().all()}
    now = utcnow()
    to_alert: list[_AlertItem] = []
    to_announce_recovery: list[_AlertItem] = []
    threshold = max(1, settings.health_check_alert_after_failures)

    for check in CHECKS:
        result = await _run_probe(check, db)
        row = existing.get(check.name)
        if row is None:
            row = SystemHealthCheck(name=check.name, status=STATUS_UNKNOWN, consecutive_failures=0, checked_at=now, changed_at=now)
            db.add(row)
            previous = None
        else:
            previous = row.status

        row.label = check.label
        row.category = check.category
        row.severity = check.severity
        row.status = result.status
        row.summary = result.summary
        row.detail = result.detail
        row.latency_ms = result.latency_ms
        row.checked_at = now
        if result.status in UNHEALTHY_STATUSES:
            row.consecutive_failures = (row.consecutive_failures or 0) + 1
        else:
            row.consecutive_failures = 0

        if previous != result.status:
            row.changed_at = now
            db.add(
                SystemHealthEvent(
                    check_name=check.name,
                    previous_status=previous,
                    status=result.status,
                    summary=result.summary,
                    detail=result.detail,
                    created_at=now,
                )
            )
            if result.status == STATUS_OK and previous in UNHEALTHY_STATUSES:
                row.alerted_at = None
                to_announce_recovery.append(_AlertItem(check.name, check.label, result.status, result.summary, result.detail))
            elif previous in UNHEALTHY_STATUSES and result.status == STATUS_SKIPPED:
                # The integration was switched off; that is a resolution, not a
                # new alarm, and it must not keep the old alert open.
                row.alerted_at = None

        if (
            alert
            and trigger == "schedule"
            and _needs_alert(check, row)
            and row.consecutive_failures >= threshold
            and not _cooldown_active(row, now)
        ):
            to_alert.append(_AlertItem(check.name, check.label, result.status, result.summary, result.detail))

    cutoff = now - timedelta(days=max(1, settings.health_check_event_retention_days))
    await db.execute(delete(SystemHealthEvent).where(SystemHealthEvent.created_at < cutoff))
    await db.commit()

    if to_alert:
        sent = await send_telegram_message(_format_alert_message(to_alert, now))
        if sent:
            # Update by statement: the rows are expired after the commit and
            # ``alert_count + 1`` has to happen in the database anyway.
            await db.execute(
                update(SystemHealthCheck)
                .where(SystemHealthCheck.name.in_([item.name for item in to_alert]))
                .values(alerted_at=now, alert_count=SystemHealthCheck.alert_count + 1)
            )
            await db.commit()
    if to_announce_recovery:
        await send_telegram_message(_format_recovery_message(to_announce_recovery, now))

    return await snapshot(db)


async def snapshot(db: AsyncSession, *, events: int = 25) -> dict:
    """The current state plus the most recent transitions, for the admin page.

    Returns plain dictionaries rather than ORM rows: ``run_checks`` calls this
    right after a commit, and an expired entity would need a lazy refresh that
    async SQLAlchemy cannot perform outside the greenlet of an awaited query.
    ``populate_existing`` makes the SELECT itself refresh every column.
    """
    rows = list(
        (await db.execute(select(SystemHealthCheck).execution_options(populate_existing=True))).scalars().all()
    )
    event_rows = list(
        (
            await db.execute(
                select(SystemHealthEvent)
                .order_by(SystemHealthEvent.created_at.desc())
                .limit(max(1, events))
            )
        )
        .scalars()
        .all()
    )
    now = utcnow()
    rows.sort(key=lambda row: (SEVERITY_ORDER.get(row.severity, 9), STATUS_ORDER.get(row.status, 9), row.label))
    checks = [
        {
            "name": row.name,
            "label": row.label,
            "category": row.category,
            "severity": row.severity,
            "status": row.status,
            "summary": row.summary,
            "detail": row.detail,
            "latency_ms": row.latency_ms,
            "consecutive_failures": row.consecutive_failures,
            "checked_at": row.checked_at,
            "changed_at": row.changed_at,
        }
        for row in rows
    ]
    history = [
        {
            "id": event.id,
            "check_name": event.check_name,
            "previous_status": event.previous_status,
            "status": event.status,
            "summary": event.summary,
            "detail": event.detail,
            "created_at": event.created_at,
        }
        for event in event_rows
    ]
    newest = max((row.checked_at for row in rows), default=None)
    stale_after = max(60, settings.health_check_interval_seconds * 3)
    return {
        "generated_at": now,
        "overall_status": overall_status({row.status for row in rows}),
        "stale": newest is None or (now - newest).total_seconds() > stale_after,
        "last_checked_at": newest,
        "checks": checks,
        "events": history,
    }


def overall_status(statuses: set[str]) -> str:
    """One word for the dashboard: down beats degraded beats everything else."""
    if not statuses:
        return STATUS_UNKNOWN
    if STATUS_DOWN in statuses:
        return STATUS_DOWN
    if STATUS_DEGRADED in statuses:
        return STATUS_DEGRADED
    return STATUS_OK


async def health_summary(db: AsyncSession) -> dict:
    """Cheap counts for the public ``/health`` endpoint.

    Deliberately names nothing: the endpoint is unauthenticated, and "which
    tenant link is broken" is not public information.
    """
    rows = list((await db.execute(select(SystemHealthCheck.name, SystemHealthCheck.status))).all())
    down = sum(1 for _, status in rows if status == STATUS_DOWN)
    degraded = sum(1 for _, status in rows if status == STATUS_DEGRADED)
    if not rows:
        overall = STATUS_UNKNOWN
    elif down:
        overall = STATUS_DOWN
    elif degraded:
        overall = STATUS_DEGRADED
    else:
        overall = STATUS_OK
    return {"overall": overall, "down": down, "degraded": degraded, "checks": len(rows)}
