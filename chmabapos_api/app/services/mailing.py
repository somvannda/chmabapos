"""Audience selection and delivery for the admin Mailing tool.

The admin picks a segment of merchants who stalled somewhere in onboarding,
writes (or asks AI to draft) a message, and sends it manually. Every send is
recorded per recipient and unsubscribes are honoured permanently.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import and_, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.email import send_marketing_email
from app.models import Company, EmailSend, EmailSuppression, Membership, Order, Store, User
from app.security import ALGORITHM

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
    """Send one message to a segment (or a single address) and log each result."""
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
    sent = failed = skipped = 0
    for user in recipients:
        if user.email.strip().lower() in blocked:
            skipped += 1
            continue
        values = merge_values(user, company_names.get(user.id))
        personal_subject = render_merge(subject, values, escape=False)
        personal_html = render_merge(body_html, values, escape=True)
        token = create_unsubscribe_token(user.email)
        ok = await send_marketing_email(user.email, personal_subject, personal_html, unsubscribe_token=token)
        db.add(
            EmailSend(
                user_id=user.id,
                template_id=template_id,
                recipient_email=user.email,
                subject=personal_subject,
                body_html=personal_html,
                status="sent" if ok else "failed",
                error=None if ok else "SMTP delivery failed",
                sent_by=actor_id,
            )
        )
        if ok:
            sent += 1
        else:
            failed += 1
    await db.commit()
    return {"recipients": len(recipients), "sent": sent, "failed": failed, "skipped": skipped, "test": bool(only_email)}
