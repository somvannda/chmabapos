"""Daily operations digest posted to the internal Telegram group.

Aggregates the previous local day (default ``Asia/Phnom_Penh``, UTC+7) from the
``platform_activities`` feed plus the core tables, and posts one readable recap:
signups, logins, new workspaces, sales and billing.

Run from a scheduler at 22:00 local, e.g. ``0 15 * * *`` UTC if the host clock
is UTC. The job is read-only and safe to run more than once.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    BillingPayment,
    Company,
    Order,
    PlatformActivity,
    Refund,
    Store,
)
from app.telegram import send_telegram_message

SIGNUP_EVENTS = ("user.registered", "user.google_signup")
LOGIN_EVENTS = ("user.logged_in", "user.google_login")
FALLBACK_TZ = timezone(timedelta(hours=7))


def digest_timezone():
    """IANA zone for the digest day boundary, with an exact UTC+7 fallback.

    Cambodia has no DST, so the fallback is identical to ``Asia/Phnom_Penh`` and
    keeps Windows hosts (which lack the IANA database) working.
    """
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(settings.telegram_digest_timezone)
    except Exception:
        return FALLBACK_TZ


def day_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """UTC [start, end) bounds of the current local calendar day."""
    tz = digest_timezone()
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(tz)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc), (start_local + timedelta(days=1)).astimezone(timezone.utc)


def _money(value: Decimal | None) -> str:
    return f"{(value or Decimal('0.00')).quantize(Decimal('0.01')):,.2f}"


async def _count_activities(db: AsyncSession, event_types: tuple[str, ...], start: datetime, end: datetime) -> int:
    return await db.scalar(
        select(func.count(PlatformActivity.id)).where(
            PlatformActivity.event_type.in_(event_types),
            PlatformActivity.created_at >= start,
            PlatformActivity.created_at < end,
        )
    ) or 0


async def collect_daily_stats(db: AsyncSession, *, now: datetime | None = None) -> dict:
    start, end = day_window(now)
    tz = digest_timezone()

    signups = await _count_activities(db, SIGNUP_EVENTS, start, end)
    email_signups = await _count_activities(db, ("user.registered",), start, end)
    google_signups = await _count_activities(db, ("user.google_signup",), start, end)
    verified = await _count_activities(db, ("user.email_verified",), start, end)
    logins = await _count_activities(db, LOGIN_EVENTS, start, end)
    unique_logins = await db.scalar(
        select(func.count(func.distinct(PlatformActivity.user_id))).where(
            PlatformActivity.event_type.in_(LOGIN_EVENTS),
            PlatformActivity.user_id.is_not(None),
            PlatformActivity.created_at >= start,
            PlatformActivity.created_at < end,
        )
    ) or 0
    active_users = await db.scalar(
        select(func.count(func.distinct(PlatformActivity.user_id))).where(
            PlatformActivity.user_id.is_not(None),
            PlatformActivity.created_at >= start,
            PlatformActivity.created_at < end,
        )
    ) or 0
    team_added = await _count_activities(db, ("team.invitation_accepted",), start, end)

    new_companies = await db.scalar(select(func.count(Company.id)).where(Company.created_at >= start, Company.created_at < end)) or 0
    new_stores = await db.scalar(select(func.count(Store.id)).where(Store.created_at >= start, Store.created_at < end)) or 0

    orders_paid = await db.scalar(select(func.count(Order.id)).where(Order.paid_at.is_not(None), Order.paid_at >= start, Order.paid_at < end)) or 0
    revenue = await db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.paid_at.is_not(None), Order.paid_at >= start, Order.paid_at < end))
    refund_count = await db.scalar(select(func.count(Refund.id)).where(Refund.created_at >= start, Refund.created_at < end)) or 0
    refund_total = await db.scalar(select(func.coalesce(func.sum(Refund.total), 0)).where(Refund.created_at >= start, Refund.created_at < end))
    plan_payments = await db.scalar(
        select(func.count(BillingPayment.id)).where(BillingPayment.status == "paid", BillingPayment.fulfilled_at >= start, BillingPayment.fulfilled_at < end)
    ) or 0
    plan_revenue = await db.scalar(
        select(func.coalesce(func.sum(BillingPayment.amount), 0)).where(BillingPayment.status == "paid", BillingPayment.fulfilled_at >= start, BillingPayment.fulfilled_at < end)
    )

    return {
        "date": start.astimezone(tz).date().isoformat(),
        "timezone": str(settings.telegram_digest_timezone),
        "signups": signups,
        "email_signups": email_signups,
        "google_signups": google_signups,
        "verified": verified,
        "logins": logins,
        "unique_logins": unique_logins,
        "active_users": active_users,
        "team_added": team_added,
        "new_companies": new_companies,
        "new_stores": new_stores,
        "orders_paid": orders_paid,
        "revenue": _money(revenue),
        "refunds": refund_count,
        "refund_total": _money(refund_total),
        "plan_payments": plan_payments,
        "plan_revenue": _money(plan_revenue),
    }


def render_digest(stats: dict) -> str:
    lines = [
        f"Chmaba daily recap - {stats['date']}",
        "",
        f"New signups: {stats['signups']} (email {stats['email_signups']}, Google {stats['google_signups']})",
        f"Email verified: {stats['verified']}",
        f"Logins: {stats['logins']} (unique users {stats['unique_logins']})",
        f"Active users: {stats['active_users']}",
        f"Team members added: {stats['team_added']}",
        "",
        f"New companies: {stats['new_companies']}",
        f"New stores: {stats['new_stores']}",
        "",
        f"Paid orders: {stats['orders_paid']}",
        f"Sales revenue: {stats['revenue']}",
        f"Refunds: {stats['refunds']} ({stats['refund_total']})",
        f"Plan payments: {stats['plan_payments']} ({stats['plan_revenue']})",
        "",
        f"Generated 22:00 {stats['timezone']}",
    ]
    return "\n".join(lines)


async def run_daily_digest(db: AsyncSession, *, now: datetime | None = None) -> dict:
    stats = await collect_daily_stats(db, now=now)
    sent = await send_telegram_message(render_digest(stats))
    stats["sent"] = sent
    return stats
