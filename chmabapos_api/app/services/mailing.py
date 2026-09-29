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
from app.email import send_marketing_email
from app.models import Company, EmailSend, EmailSuppression, MailingDripDelivery, Membership, Order, PlatformSetting, Store, User
from app.security import ALGORITHM
from app.services import mail as mail_service

UNSUBSCRIBE_TOKEN_TYPE = "unsubscribe"
DEFAULT_SEND_LIMIT = 200
MAX_SEND_LIMIT = 500

AUDIENCES: dict[str, str] = {
    "no_workspace": "Confirmed email but never set up a workspace",
    "unverified": "Signed up but never confirmed their email",
    "no_sales": "Set up a workspace but never recorded a sale",
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
)

_TOKEN_PATTERN = re.compile(r"\{\{\s*(name|full_name|store|email)\s*\}\}", re.IGNORECASE)


def merge_values(user: User, company_name: str | None = None) -> dict[str, str]:
    full_name = (user.full_name or "").strip()
    first_name = full_name.split()[0] if full_name else ""
    return {
        "{{name}}": first_name or "there",
        "{{full_name}}": full_name or "there",
        "{{store}}": (company_name or "").strip() or "your store",
        "{{email}}": user.email or "",
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


def audience_condition(audience: str):
    if audience == "no_workspace":
        return and_(User.is_email_verified.is_(True), ~_active_membership_exists())
    if audience == "unverified":
        return User.is_email_verified.is_(False)
    if audience == "no_sales":
        return and_(User.is_email_verified.is_(True), _active_membership_exists(), ~_any_sale_exists())
    return true()


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
        values = merge_values(user, company_names.get(user.id))
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
            ok = await send_marketing_email(
                user.email, personal_subject, personal_html, unsubscribe_token=create_unsubscribe_token(user.email)
            )
            row.status = "sent" if ok else "failed"
            row.error = None if ok else "Delivery failed"
            row.provider = await current_provider(db)
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


async def send_pending_emails(db: AsyncSession, *, limit: int = 50, now: datetime | None = None) -> dict:
    """Deliver queued messages, retrying failures with backoff.

    Safe to run often: rows are claimed by due time and only leave ``queued``
    when they are sent, exhausted, or the recipient has unsubscribed.
    """
    now = now or utc_now()
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
        blocked = await suppressed_emails(db, [row.recipient_email for row in rows])
        provider = await current_provider(db)
        for row in rows:
            stats["processed"] += 1
            if row.recipient_email.strip().lower() in blocked:
                row.status = "skipped"
                row.error = "Recipient unsubscribed before sending"
                row.next_attempt_at = None
                stats["skipped"] += 1
                continue
            ok = await send_marketing_email(
                row.recipient_email,
                row.subject,
                row.body_html,
                unsubscribe_token=create_unsubscribe_token(row.recipient_email),
            )
            row.attempts += 1
            row.last_attempt_at = now
            row.provider = provider
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


def default_drip_config() -> dict:
    """Sensible starter sequence an admin can edit or disable."""
    base = settings.frontend_url.rstrip("/")
    link = '<a href="' + base + '">'
    return {
        "max_age_days": DRIP_DEFAULT_MAX_AGE_DAYS,
        "steps": [
            {
                "id": "day1",
                "day_offset": 1,
                "audience": "no_workspace",
                "enabled": True,
                "subject": "{{name}}, finish setting up your Chmaba store",
                "body_html": "<p>Hi {{name}},</p><p>You created your Chmaba account but have not set up a store yet. It takes about two minutes.</p><p>" + link + "Finish setting up</a></p>",
            },
            {
                "id": "day3",
                "day_offset": 3,
                "audience": "no_workspace",
                "enabled": True,
                "subject": "Need a hand getting started, {{name}}?",
                "body_html": "<p>Hi {{name}},</p><p>Still with us? Setting up takes a couple of minutes and there is no cost to start.</p><p>" + link + "Set up your store</a></p>",
            },
            {
                "id": "day7",
                "day_offset": 7,
                "audience": "no_workspace",
                "enabled": False,
                "subject": "{{name}}, your store is still waiting",
                "body_html": "<p>Hi {{name}},</p><p>Your Chmaba account is ready whenever you are. Come back and start selling.</p><p>" + link + "Open Chmaba</a></p>",
            },
        ],
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


def _normalise_config(raw) -> dict:
    if not isinstance(raw, dict):
        return default_drip_config()
    try:
        max_age_days = max(1, min(int(raw.get("max_age_days", DRIP_DEFAULT_MAX_AGE_DAYS)), 365))
    except (TypeError, ValueError):
        max_age_days = DRIP_DEFAULT_MAX_AGE_DAYS
    steps = [step for step in (_normalise_step(item) for item in (raw.get("steps") or [])) if step]
    return {"max_age_days": max_age_days, "steps": steps}


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


async def run_mailing_drip(db: AsyncSession, *, now: datetime | None = None) -> dict:
    """Send each enabled drip step to newly stalled signups, once per person.

    Idempotent: the ``mailing_drip_deliveries`` ledger is unique per
    (user, step), so re-running the job never double-emails anyone.
    """
    now = now or utc_now()
    config = await load_drip_config(db)
    floor = now - timedelta(days=config["max_age_days"])
    stats = {"queued": 0, "skipped": 0, "steps": 0}
    for step in config["steps"]:
        if not step["enabled"]:
            continue
        stats["steps"] += 1
        cutoff = now - timedelta(days=step["day_offset"])
        already = (
            select(MailingDripDelivery.id)
            .where(MailingDripDelivery.user_id == User.id, MailingDripDelivery.step_id == step["id"])
            .exists()
        )
        query = (
            build_audience_query(step["audience"])
            .where(User.created_at <= cutoff, User.created_at >= floor, ~already)
            .limit(MAX_SEND_LIMIT)
        )
        recipients = list((await db.execute(query)).scalars().all())
        blocked = await suppressed_emails(db, [user.email for user in recipients])
        company_names = await _company_names_for(db, [user.id for user in recipients])
        for user in recipients:
            if user.email.strip().lower() in blocked:
                stats["skipped"] += 1
                continue
            values = merge_values(user, company_names.get(user.id))
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
    await db.commit()
    return stats
