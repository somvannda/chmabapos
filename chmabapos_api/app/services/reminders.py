"""Billing renewal reminders (in-app + email) before a paid period ends.

Plans are prepaid and renew manually, so owners get nudged at -7, -3 and -1
days before ``ends_at``. Each (subscription, days-before) reminder fires at
most once; ownership of the send is recorded in ``billing_reminders``.

Reminders reference the next plan (the scheduled downgrade target, or the
current plan) and its renewal amount. A cancel scheduled to Free is surfaced
as a last chance to renew instead.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import FREE_PLAN_CODE
from app.config import settings
from app.email import send_email
from app.models import BillingReminder, Company, Membership, Notification, Plan, Store, Subscription, User
from app.services.pricing import period_label, period_total_label

REMINDER_OFFSETS: tuple[int, ...] = (7, 3, 1)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _notify_owners(db: AsyncSession, company_id: UUID, title: str, body: str) -> None:
    store_id = await db.scalar(select(Store.id).where(Store.company_id == company_id, Store.is_active.is_(True)).limit(1))
    if store_id is None:
        return
    user_ids = (await db.execute(select(Membership.user_id).where(Membership.company_id == company_id, Membership.role == "owner", Membership.status == "active"))).scalars().all()
    for user_id in user_ids:
        db.add(Notification(store_id=store_id, user_id=user_id, type="billing", title=title, body=body))


async def _capacity_warning(db: AsyncSession, company_id: UUID, target_plan: Plan) -> str | None:
    """One-line warning of what will be paused if the plan lapses or downgrades.

    Tells the owner *before* expiry how many stores and staff the target plan
    cannot keep, so the outcome is not a surprise.
    """
    active_stores = await db.scalar(select(func.count(Store.id)).where(Store.company_id == company_id, Store.is_active.is_(True))) or 0
    owners = await db.scalar(select(func.count(Membership.id)).where(Membership.company_id == company_id, Membership.role == "owner", Membership.status == "active")) or 0
    active_staff = await db.scalar(select(func.count(Membership.id)).where(Membership.company_id == company_id, Membership.role != "owner", Membership.status == "active")) or 0
    stores_at_risk = max(active_stores - target_plan.max_stores, 0)
    if target_plan.code == FREE_PLAN_CODE:
        staff_at_risk = active_staff
    else:
        staff_at_risk = max(active_staff - max(target_plan.max_members - owners, 0), 0)
    parts: list[str] = []
    if stores_at_risk:
        parts.append(f"{stores_at_risk} store{'s' if stores_at_risk != 1 else ''}")
    if staff_at_risk:
        parts.append(f"{staff_at_risk} team member{'s' if staff_at_risk != 1 else ''}")
    if not parts:
        return None
    return f"If you don't renew, {' and '.join(parts)} will be paused. Your data is safe."


async def _deliver_reminder(db: AsyncSession, subscription: Subscription, offset: int) -> None:
    company = await db.get(Company, subscription.company_id)
    if company is None:
        return
    current_plan = await db.get(Plan, subscription.plan_code)
    if current_plan is None:
        return
    ends_label = (subscription.ends_at or utc_now()).date().isoformat()
    cancelling = subscription.scheduled_plan_code == FREE_PLAN_CODE
    next_code = subscription.plan_code if (cancelling or not subscription.scheduled_plan_code) else subscription.scheduled_plan_code
    next_plan = await db.get(Plan, next_code)
    if next_plan is None:
        return
    amount = period_total_label(next_plan.monthly_price, subscription.billing_cycle)
    cycle = period_label(subscription.billing_cycle)
    if cancelling:
        title = f"Your {current_plan.name} plan ends {ends_label}"
        subject = f"{current_plan.name} plan ending {ends_label} - renew to stay on Chmaba"
        body_lines = [
            f"Your {current_plan.name} plan ends on {ends_label} and you've scheduled to move to the Free plan.",
            "If you renew before then you keep your current plan without interruption.",
            f"Renew {current_plan.name} for ${amount} ({cycle}) from Billing & plans in your workspace.",
        ]
    else:
        if next_code == subscription.plan_code:
            title = f"Renew {next_plan.name} - ends {ends_label}"
            subject = f"Renew your {next_plan.name} plan - ${amount} {cycle}"
            body_lines = [
                f"Your {current_plan.name} plan ends on {ends_label}.",
                f"Renew {next_plan.name} for ${amount} ({cycle}) to keep your workspace running without interruption.",
            ]
        else:
            title = f"{current_plan.name} to {next_plan.name} on {ends_label}"
            subject = f"Renew your {next_plan.name} plan - ${amount} {cycle}"
            body_lines = [
                f"Your {current_plan.name} plan ends on {ends_label} and you've scheduled a switch to {next_plan.name}.",
                f"Renew {next_plan.name} for ${amount} ({cycle}) so the switch happens without interruption.",
            ]
    warning = await _capacity_warning(db, company.id, next_plan)
    if warning:
        body_lines.append(warning)
    body_lines.append(f"Open Chmaba and go to Billing & plans to pay: {settings.frontend_url}")
    body = "\n\n".join(body_lines)
    await _notify_owners(db, company.id, title, " ".join(body_lines[:2]))

    owners = (
        await db.execute(
            select(User.email).join(Membership, Membership.user_id == User.id).where(
                Membership.company_id == company.id, Membership.role == "owner", Membership.status == "active"
            )
        )
    ).scalars().all()
    for email in owners:
        await send_email(email, subject, body)
    db.add(BillingReminder(subscription_id=subscription.id, days_before=offset))


async def run_reminder_job(db: AsyncSession) -> dict:
    """Send due reminders for active paid plans ending within the offsets."""
    now = utc_now()
    stats = {"reminders": 0}
    for offset in REMINDER_OFFSETS:
        cutoff = now + timedelta(days=offset)
        due = (
            await db.execute(
                select(Subscription).where(
                    Subscription.status == "active",
                    Subscription.plan_code != FREE_PLAN_CODE,
                    Subscription.ends_at.is_not(None),
                    Subscription.ends_at > now,
                    Subscription.ends_at <= cutoff,
                    ~select(BillingReminder.id)
                    .where(BillingReminder.subscription_id == Subscription.id, BillingReminder.days_before == offset)
                    .exists(),
                )
            )
        ).scalars().all()
        for subscription in due:
            await _deliver_reminder(db, subscription, offset)
            stats["reminders"] += 1
    return stats
