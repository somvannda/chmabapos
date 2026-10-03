"""Audience selection and delivery for the admin Mailing tool.

The admin picks a segment of merchants who stalled somewhere in onboarding,
writes (or asks AI to draft) a message, and sends it manually. Every send is
recorded per recipient and unsubscribes are honoured permanently.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import and_, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.email import html_to_text, send_email_with_id, send_marketing_email_with_id, unsubscribe_url
from app.models import Company, EmailSend, EmailSuppression, EmailVerificationToken, MailingDripDelivery, Membership, Order, PlatformSetting, Product, Store, User
from app.security import ALGORITHM
from app.services import mail as mail_service
from app.services.onboarding_emails import BASE_TOKEN, ONBOARDING_EMAILS
from app.services.sale_emails import TRANSACTIONAL_SOURCES

UNSUBSCRIBE_TOKEN_TYPE = "unsubscribe"
DEFAULT_SEND_LIMIT = 200
MAX_SEND_LIMIT = 500

AUDIENCES: dict[str, str] = {
    "unverified": "Signed up but never confirmed their email",
    "no_workspace": "Confirmed email but never set up a workspace",
    "no_product": "Set up a workspace but never added a product",
    "no_sales": "Added a product but never recorded a sale",
    "all": "Every active account (safety net)",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def audience_catalog() -> list[dict[str, str]]:
    return [{"code": code, "label": label} for code, label in AUDIENCES.items()]


# Personalization tokens an operator can drop into a subject or body. Resolved
# per recipient at send time; unknown or empty values fall back to something
# readable rather than leaving "{{name}}" in an inbox.
MERGE_TOKENS: tuple[dict[str, str], ...] = (
    {"token": "{{name}}", "label": "First name", "sample": "Sokha"},
    {"token": "{{full_name}}", "label": "Full name", "sample": "Sokha Chan"},
    {"token": "{{store}}", "label": "Store / business name", "sample": "Sokha Mart"},
    {"token": "{{email}}", "label": "Email address", "sample": "sokha@example.com"},
    {"token": "{{unsubscribe}}", "label": "Unsubscribe link", "sample": "https://chmaba.com/api/v1/email/unsubscribe?token=..."},
)

_TOKEN_PATTERN = re.compile(r"\{\{\s*(name|full_name|store|email|unsubscribe)\s*\}\}", re.IGNORECASE)


def merge_values(user: User, company_name: str | None = None, unsubscribe_url_value: str | None = None) -> dict[str, str]:
    full_name = (user.full_name or "").strip()
    first_name = full_name.split()[0] if full_name else ""
    return {
        "{{name}}": first_name or "there",
        "{{full_name}}": full_name or "there",
        "{{store}}": (company_name or "").strip() or "your store",
        "{{email}}": user.email or "",
        # A signed, one-click opt-out URL. Falls back to the storefront when no
        # per-recipient token is available (e.g. a merge preview).
        "{{unsubscribe}}": unsubscribe_url_value or settings.frontend_url,
    }


def render_merge(text: str, values: dict[str, str], *, escape: bool) -> str:
    """Replace ``{{token}}`` placeholders with per-recipient values.

    ``escape=True`` is used for HTML bodies so a name like ``A & B`` cannot
    break the markup; subjects are plain text and pass ``escape=False``.
    """

    def replace(match: re.Match[str]) -> str:
        value = values.get("{{" + match.group(1).lower() + "}}", "")
        return html.escape(value) if escape else value

    return _TOKEN_PATTERN.sub(replace, text or "")


async def _company_names_for(db: AsyncSession, user_ids: list) -> dict:
    """First active company name per user, in a single query (avoids N+1)."""
    if not user_ids:
        return {}
    rows = (
        await db.execute(
            select(Membership.user_id, Company.name)
            .join(Company, Company.id == Membership.company_id)
            .where(Membership.user_id.in_(user_ids), Membership.status == "active")
            .order_by(Membership.created_at)
        )
    ).all()
    names: dict = {}
    for user_id, name in rows:
        names.setdefault(user_id, name)
    return names


def create_unsubscribe_token(email: str) -> str:
    """A signed, non-expiring token that lets a recipient opt out."""
    return jwt.encode({"sub": email.strip().lower(), "type": UNSUBSCRIBE_TOKEN_TYPE}, settings.jwt_secret, algorithm=ALGORITHM)


def read_unsubscribe_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != UNSUBSCRIBE_TOKEN_TYPE:
        return None
    email = payload.get("sub")
    return email.strip().lower() if isinstance(email, str) and "@" in email else None


def _active_membership_exists():
    return select(Membership.id).where(Membership.user_id == User.id, Membership.status == "active").exists()


def _any_sale_exists():
    """True when the user's workspace(s) have recorded at least one order."""
    return (
        select(Order.id)
        .join(Store, Store.id == Order.store_id)
        .join(Membership, Membership.company_id == Store.company_id)
        .where(Membership.user_id == User.id)
        .exists()
    )


def _real_product_exists():
    """True when the user's workspace(s) have a product they added themselves.

    Seeded sample products do not count, so ``no_product`` keeps nudging a
    merchant to put their own catalogue in even though the demo items are
    sellable.
    """
    return (
        select(Product.id)
        .join(Membership, Membership.company_id == Product.company_id)
        .where(
            Membership.user_id == User.id,
            Membership.status == "active",
            Product.is_active.is_(True),
            Product.is_sample.is_(False),
        )
        .exists()
    )


def audience_condition(audience: str):
    if audience == "no_workspace":
        return and_(User.is_email_verified.is_(True), ~_active_membership_exists())
    if audience == "unverified":
        return User.is_email_verified.is_(False)
    if audience == "no_product":
        return and_(User.is_email_verified.is_(True), _active_membership_exists(), ~_real_product_exists())
    if audience == "no_sales":
        return and_(User.is_email_verified.is_(True), _active_membership_exists(), _real_product_exists(), ~_any_sale_exists())
    return true()


def audience_advance_subquery(audience: str):
    """First moment each user moved past ``audience``, as (user_id, advance_at).

    Scores a drip step with a time window: only recipients whose first
    advancement event happened shortly after *that particular send* are
    counted, so a stage with two steps no longer double-counts the later one.
    Returns ``None`` when there is no measurable event for the audience.
    """
    if audience == "unverified":
        return (
            select(EmailVerificationToken.user_id.label("user_id"), func.min(EmailVerificationToken.used_at).label("advance_at"))
            .where(EmailVerificationToken.used_at.is_not(None))
            .group_by(EmailVerificationToken.user_id)
            .subquery()
        )
    if audience == "no_workspace":
        return (
            select(Membership.user_id.label("user_id"), func.min(Membership.created_at).label("advance_at"))
            .where(Membership.status == "active")
            .group_by(Membership.user_id)
            .subquery()
        )
    if audience == "no_product":
        return (
            select(Membership.user_id.label("user_id"), func.min(Product.created_at).label("advance_at"))
            .select_from(Membership)
            .join(Product, Product.company_id == Membership.company_id)
            .where(Membership.status == "active", Product.is_active.is_(True), Product.is_sample.is_(False))
            .group_by(Membership.user_id)
            .subquery()
        )
    if audience == "no_sales":
        return (
            select(Membership.user_id.label("user_id"), func.min(Order.created_at).label("advance_at"))
            .select_from(Membership)
            .join(Store, Store.company_id == Membership.company_id)
            .join(Order, Order.store_id == Store.id)
            .where(Membership.status == "active", Order.status == "paid")
            .group_by(Membership.user_id)
            .subquery()
        )
    return None


def build_audience_query(
    audience: str,
    *,
    min_age_hours: int | None = None,
    max_age_days: int | None = None,
    search: str | None = None,
):
    now = utc_now()
    conditions = [User.is_active.is_(True), audience_condition(audience)]
    if min_age_hours:
        conditions.append(User.created_at <= now - timedelta(hours=min_age_hours))
    if max_age_days:
        conditions.append(User.created_at >= now - timedelta(days=max_age_days))
    if search:
        conditions.append(User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%"))
    return select(User).where(*conditions).order_by(User.created_at.desc())


async def audience_breakdown(db: AsyncSession, *, min_age_hours: int | None = None, max_age_days: int | None = None) -> dict:
    """Counts per segment so the admin can pick a target before composing."""
    segments = []
    for code, label in AUDIENCES.items():
        query = build_audience_query(code, min_age_hours=min_age_hours, max_age_days=max_age_days)
        count = await db.scalar(select(func.count()).select_from(query.subquery()))
        segments.append({"code": code, "label": label, "count": count or 0})
    return {"segments": segments}


async def resolve_recipients(
    db: AsyncSession,
    *,
    audience: str,
    min_age_hours: int | None = None,
    max_age_days: int | None = None,
    search: str | None = None,
    limit: int = DEFAULT_SEND_LIMIT,
) -> list[User]:
    query = build_audience_query(audience, min_age_hours=min_age_hours, max_age_days=max_age_days, search=search).limit(limit)
    return list((await db.execute(query)).scalars().all())


async def suppressed_emails(db: AsyncSession, emails: list[str]) -> set[str]:
    if not emails:
        return set()
    lowered = [email.strip().lower() for email in emails]
    rows = (
        await db.execute(select(EmailSuppression.email).where(func.lower(EmailSuppression.email).in_(lowered)))
    ).scalars().all()
    return {row.strip().lower() for row in rows}


async def suppress(db: AsyncSession, email: str, *, reason: str = "unsubscribed") -> None:
    """Idempotently add an address to the suppression list."""
    cleaned = email.strip().lower()
    if not cleaned:
        return
    existing = await db.scalar(select(EmailSuppression.id).where(func.lower(EmailSuppression.email) == cleaned))
    if existing is None:
        db.add(EmailSuppression(email=cleaned, reason=reason))
        await db.commit()


async def send_campaign(
    db: AsyncSession,
    *,
    actor_id,
    subject: str,
    body_html: str,
    audience: str,
    template_id=None,
    min_age_hours: int | None = None,
    max_age_days: int | None = None,
    search: str | None = None,
    limit: int = DEFAULT_SEND_LIMIT,
    only_email: str | None = None,
) -> dict:
    """Queue a message for a segment, or send a single test immediately.

    Segment sends are queued so the request returns fast and delivery survives
    transient provider failures; a single test send is delivered inline so the
    operator gets immediate feedback.
    """
    limit = max(1, min(limit, MAX_SEND_LIMIT))
    if only_email:
        recipient = await db.scalar(select(User).where(func.lower(User.email) == only_email.strip().lower(), User.is_active.is_(True)))
        recipients = [recipient] if recipient else []
    else:
        recipients = await resolve_recipients(
            db, audience=audience, min_age_hours=min_age_hours, max_age_days=max_age_days, search=search, limit=limit
        )

    blocked = await suppressed_emails(db, [user.email for user in recipients])
    company_names = await _company_names_for(db, [user.id for user in recipients])
    queued = sent = failed = skipped = 0
    for user in recipients:
        if user.email.strip().lower() in blocked:
            skipped += 1
            continue
        values = merge_values(user, company_names.get(user.id), unsubscribe_url(create_unsubscribe_token(user.email)))
        personal_subject = render_merge(subject, values, escape=False)
        personal_html = render_merge(body_html, values, escape=True)
        row = EmailSend(
            user_id=user.id,
            template_id=template_id,
            recipient_email=user.email,
            subject=personal_subject,
            body_html=personal_html,
            sent_by=actor_id,
            source="manual",
        )
        if only_email:
            ok, message_id = await send_marketing_email_with_id(
                user.email, personal_subject, personal_html, unsubscribe_token=create_unsubscribe_token(user.email)
            )
            row.status = "sent" if ok else "failed"
            row.error = None if ok else "Delivery failed"
            row.provider = await current_provider(db)
            row.provider_message_id = message_id
            row.attempts = 1
            row.last_attempt_at = utc_now()
            sent, failed = (sent + 1, failed) if ok else (sent, failed + 1)
        else:
            row.status = "queued"
            queued += 1
        db.add(row)
    await db.commit()
    return {
        "recipients": len(recipients),
        "queued": queued,
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "test": bool(only_email),
    }


# ---------------------------------------------------------------------------
# Send queue
# ---------------------------------------------------------------------------

MAILING_MAX_ATTEMPTS = 4
MAILING_BACKOFF_MINUTES = (1, 5, 15, 60)


async def current_provider(db: AsyncSession) -> str:
    """The transport that will be used for the next send."""
    return mail_service.resolve_provider(await mail_service.load_mail_settings(db))


async def queued_count(db: AsyncSession) -> int:
    return await db.scalar(select(func.count(EmailSend.id)).where(EmailSend.status == "queued")) or 0


def retry_delay_minutes(attempts: int) -> int:
    return MAILING_BACKOFF_MINUTES[min(max(attempts - 1, 0), len(MAILING_BACKOFF_MINUTES) - 1)]


MAILING_QUEUE_LOCK_KEY = 8314159265


async def send_pending_emails(db: AsyncSession, *, limit: int = 50, now: datetime | None = None) -> dict:
    """Deliver queued messages, retrying failures with backoff.

    Safe to run often and from more than one place: a transaction-scoped
    Postgres advisory lock means only one drain runs at a time, so the in-process
    worker and a cron job may both be enabled without double-sending.
    """
    now = now or utc_now()
    if not await db.scalar(select(func.pg_try_advisory_xact_lock(MAILING_QUEUE_LOCK_KEY))):
        # Another drain is in flight; let it have the batch.
        return {"processed": 0, "sent": 0, "failed": 0, "retried": 0, "skipped": 0, "remaining": await queued_count(db)}
    batch = max(1, min(limit, MAX_SEND_LIMIT))
    rows = (
        await db.execute(
            select(EmailSend)
            .where(
                EmailSend.status == "queued",
                EmailSend.attempts < MAILING_MAX_ATTEMPTS,
                or_(EmailSend.next_attempt_at.is_(None), EmailSend.next_attempt_at <= now),
            )
            .order_by(EmailSend.created_at)
            .limit(batch)
        )
    ).scalars().all()

    stats = {"processed": 0, "sent": 0, "failed": 0, "retried": 0, "skipped": 0}
    if rows:
        # Transactional rows (receipts, sale alerts) ignore the marketing
        # unsubscribe list: the store's own toggle is their control.
        blocked = await suppressed_emails(db, [row.recipient_email for row in rows if row.source not in TRANSACTIONAL_SOURCES])
        provider = await current_provider(db)
        for row in rows:
            stats["processed"] += 1
            if row.source not in TRANSACTIONAL_SOURCES and row.recipient_email.strip().lower() in blocked:
                row.status = "skipped"
                row.error = "Recipient unsubscribed before sending"
                row.next_attempt_at = None
                stats["skipped"] += 1
                continue
            if row.source in TRANSACTIONAL_SOURCES:
                # Transactional bodies are branded HTML (see email_layout).
                # Send both parts; fall back to plain text for legacy rows.
                body = row.body_html or ""
                if "<html" in body.lower() or body.lstrip().startswith("<"):
                    ok, message_id = await send_email_with_id(row.recipient_email, row.subject, html_to_text(body), html=body)
                else:
                    ok, message_id = await send_email_with_id(row.recipient_email, row.subject, body)
            else:
                ok, message_id = await send_marketing_email_with_id(
                    row.recipient_email,
                    row.subject,
                    row.body_html,
                    unsubscribe_token=create_unsubscribe_token(row.recipient_email),
                )
            row.attempts += 1
            row.last_attempt_at = now
            row.provider = provider
            row.provider_message_id = message_id
            if ok:
                row.status = "sent"
                row.error = None
                row.next_attempt_at = None
                stats["sent"] += 1
            elif row.attempts >= MAILING_MAX_ATTEMPTS:
                row.status = "failed"
                row.error = f"Delivery failed after {row.attempts} attempts"
                row.next_attempt_at = None
                stats["failed"] += 1
            else:
                row.status = "queued"
                row.error = "Delivery failed; will retry"
                row.next_attempt_at = now + timedelta(minutes=retry_delay_minutes(row.attempts))
                stats["retried"] += 1
        await db.commit()

    stats["remaining"] = await queued_count(db)
    return stats


# ---------------------------------------------------------------------------
# Automated drip
# ---------------------------------------------------------------------------

DRIP_SETTING_KEY = "mailing_drip_sequence"
DRIP_DEFAULT_MAX_AGE_DAYS = 30
DRIP_DEFAULT_MAX_PER_RUN = 200
DRIP_DEFAULT_WINDOW = {"start_hour": 8, "end_hour": 20, "weekdays_only": True, "timezone": "Asia/Phnom_Penh"}
# Cambodia has no DST, so this matches Asia/Phnom_Penh and keeps Windows hosts
# (which lack the IANA database) working.
_DRIP_FALLBACK_TZ = timezone(timedelta(hours=7))


def drip_timezone(name):
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name or DRIP_DEFAULT_WINDOW["timezone"])
    except Exception:
        return _DRIP_FALLBACK_TZ


def within_send_window(window: dict, now: datetime) -> bool:
    """Whether ``now`` falls inside the configured local sending window."""
    local = now.astimezone(drip_timezone(window.get("timezone")))
    if window.get("weekdays_only", True) and local.weekday() >= 5:
        return False
    start = int(window.get("start_hour", 0))
    end = int(window.get("end_hour", 24))
    return start <= local.hour < end


def default_drip_config() -> dict:
    """Sensible starter sequence an admin can edit or disable.

    The steps cover every place a merchant stalls between signup and their
    first sale: an unconfirmed email, no workspace, a workspace with no real
    product, and a product that never sold. Each step targets one audience, so
    a merchant only receives the messages for the stage they are actually
    stuck at (the audiences are mutually exclusive), and the delivery ledger
    means no step is ever sent twice.

    Content lives in ``app.services.onboarding_emails`` so the same copy can be
    mirrored as editable mailing templates by ``scripts/seed.py``.
    """
    base = settings.frontend_url.rstrip("/")
    steps = [
        {
            "id": str(email["id"]),
            "day_offset": int(email["day_offset"]),
            "audience": str(email["audience"]),
            "enabled": True,
            "subject": str(email["subject"]),
            "body_html": str(email["body_html"]).replace(BASE_TOKEN, base),
        }
        for email in ONBOARDING_EMAILS
    ]
    return {
        "max_age_days": DRIP_DEFAULT_MAX_AGE_DAYS,
        "verified_only": False,
        "max_per_run": DRIP_DEFAULT_MAX_PER_RUN,
        "send_window": dict(DRIP_DEFAULT_WINDOW),
        "steps": steps,
    }


def _normalise_step(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    step_id = str(raw.get("id") or "").strip()[:60]
    subject = str(raw.get("subject") or "").strip()
    body_html = str(raw.get("body_html") or "").strip()
    if not step_id or not subject or not body_html:
        return None
    try:
        day_offset = max(0, min(int(raw.get("day_offset", 0)), 365))
    except (TypeError, ValueError):
        day_offset = 0
    audience = raw.get("audience") if raw.get("audience") in AUDIENCES else "no_workspace"
    return {
        "id": step_id,
        "day_offset": day_offset,
        "audience": audience,
        "enabled": bool(raw.get("enabled", True)),
        "subject": subject[:300],
        "body_html": body_html,
    }


def _clamp_int(value, low: int, high: int, fallback: int) -> int:
    try:
        return max(low, min(int(value), high))
    except (TypeError, ValueError):
        return fallback


def _normalise_window(raw) -> dict:
    window = raw if isinstance(raw, dict) else {}
    return {
        "start_hour": _clamp_int(window.get("start_hour", DRIP_DEFAULT_WINDOW["start_hour"]), 0, 23, DRIP_DEFAULT_WINDOW["start_hour"]),
        "end_hour": _clamp_int(window.get("end_hour", DRIP_DEFAULT_WINDOW["end_hour"]), 1, 24, DRIP_DEFAULT_WINDOW["end_hour"]),
        "weekdays_only": bool(window.get("weekdays_only", DRIP_DEFAULT_WINDOW["weekdays_only"])),
        "timezone": (str(window.get("timezone") or DRIP_DEFAULT_WINDOW["timezone"]).strip()[:60]) or DRIP_DEFAULT_WINDOW["timezone"],
    }


def _normalise_config(raw) -> dict:
    if not isinstance(raw, dict):
        return default_drip_config()
    steps = [step for step in (_normalise_step(item) for item in (raw.get("steps") or [])) if step]
    return {
        "max_age_days": _clamp_int(raw.get("max_age_days", DRIP_DEFAULT_MAX_AGE_DAYS), 1, 365, DRIP_DEFAULT_MAX_AGE_DAYS),
        "verified_only": bool(raw.get("verified_only", False)),
        "max_per_run": _clamp_int(raw.get("max_per_run", DRIP_DEFAULT_MAX_PER_RUN), 1, MAX_SEND_LIMIT, DRIP_DEFAULT_MAX_PER_RUN),
        "send_window": _normalise_window(raw.get("send_window")),
        "steps": steps,
    }


async def load_drip_config(db: AsyncSession) -> dict:
    row = await db.get(PlatformSetting, DRIP_SETTING_KEY)
    if row and row.value:
        try:
            return _normalise_config(json.loads(row.value))
        except ValueError:
            pass
    return default_drip_config()


async def save_drip_config(db: AsyncSession, config: dict) -> dict:
    normalised = _normalise_config(config)
    value = json.dumps(normalised)
    row = await db.get(PlatformSetting, DRIP_SETTING_KEY)
    if row is None:
        db.add(PlatformSetting(key=DRIP_SETTING_KEY, value=value))
    else:
        row.value = value
    await db.commit()
    return normalised


async def run_mailing_drip(db: AsyncSession, *, now: datetime | None = None, force: bool = False) -> dict:
    """Send each enabled drip step to newly stalled signups, once per person.

    Idempotent: the ``mailing_drip_deliveries`` ledger is unique per
    (user, step), so re-running the job never double-emails anyone. Respects the
    configured local send window unless ``force`` is set (the admin "Run now").
    """
    now = now or utc_now()
    config = await load_drip_config(db)
    stats = {"queued": 0, "skipped": 0, "steps": 0, "window": True}
    if not force and not within_send_window(config["send_window"], now):
        stats["window"] = False
        return stats
    floor = now - timedelta(days=config["max_age_days"])
    budget = config["max_per_run"]
    for step in config["steps"]:
        if budget <= 0:
            break
        if not step["enabled"]:
            continue
        stats["steps"] += 1
        cutoff = now - timedelta(days=step["day_offset"])
        already = (
            select(MailingDripDelivery.id)
            .where(MailingDripDelivery.user_id == User.id, MailingDripDelivery.step_id == step["id"])
            .exists()
        )
        query = build_audience_query(step["audience"]).where(User.created_at <= cutoff, User.created_at >= floor, ~already)
        if config["verified_only"]:
            query = query.where(User.is_email_verified.is_(True))
        recipients = list((await db.execute(query.limit(min(MAX_SEND_LIMIT, budget)))).scalars().all())
        blocked = await suppressed_emails(db, [user.email for user in recipients])
        company_names = await _company_names_for(db, [user.id for user in recipients])
        for user in recipients:
            if user.email.strip().lower() in blocked:
                stats["skipped"] += 1
                continue
            values = merge_values(user, company_names.get(user.id), unsubscribe_url(create_unsubscribe_token(user.email)))
            subject = render_merge(step["subject"], values, escape=False)
            body = render_merge(step["body_html"], values, escape=True)
            # The ledger is written when the step is queued, so a later run never
            # enqueues the same (person, step) twice; retries are the queue's job.
            db.add(MailingDripDelivery(user_id=user.id, step_id=step["id"]))
            db.add(
                EmailSend(
                    user_id=user.id,
                    template_id=None,
                    recipient_email=user.email,
                    subject=subject,
                    body_html=body,
                    status="queued",
                    error=None,
                    sent_by=None,
                    source="drip",
                )
            )
            stats["queued"] += 1
            budget -= 1
    await db.commit()
    return stats
