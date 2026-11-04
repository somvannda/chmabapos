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
from html import escape

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import FREE_PLAN_CODE
from app.config import settings
from app.email import app_url, username_for
from app.models import BillingReminder, Company, EmailSend, Membership, Notification, Plan, Store, Subscription, User
from app.services.billing_emails import BILLING_EXPIRY_SOURCE, BILLING_REMINDER_SOURCE, queue_billing_notice
from app.services.email_layout import data_table, transactional_email
from app.services.pricing import period_label, period_total_label

DEFAULT_REMINDER_OFFSETS: tuple[int, ...] = (7, 3, 1)


def reminder_offsets() -> tuple[int, ...]:
    """Configured reminder days, newest first; invalid input uses the default."""
    values: set[int] = set()
    for raw in (settings.billing_reminder_offsets or "").split(","):
        try:
            value = int(raw.strip())
        except ValueError:
            continue
        if 1 <= value <= 365:
            values.add(value)
    return tuple(sorted(values, reverse=True)) or DEFAULT_REMINDER_OFFSETS


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _notify_owners(db: AsyncSession, company_id: UUID, title: str, body: str, link: str | None = None) -> None:
    store_id = await db.scalar(select(Store.id).where(Store.company_id == company_id, Store.is_active.is_(True)).limit(1))
    if store_id is None:
        return
    user_ids = (await db.execute(select(Membership.user_id).where(Membership.company_id == company_id, Membership.role == "owner", Membership.status == "active"))).scalars().all()
    if not user_ids:
        return
    # Keep exactly one billing row per owner. The -7 / -3 / -1 nudges and the
    # after-expiry notice all describe the same situation, so each new one
    # replaces the last instead of stacking stale reminders into the bell.
    await db.execute(delete(Notification).where(Notification.user_id.in_(user_ids), Notification.type == "billing"))
    for user_id in user_ids:
        db.add(Notification(store_id=store_id, user_id=user_id, type="billing", title=title, body=body, link=link))


async def clear_billing_notifications(db: AsyncSession, company_id: UUID) -> None:
    """Drop owners' billing alerts once a payment lands.

    A renewal or expiry nudge is only useful until the plan is paid; leaving it
    in the bell afterwards reports a problem the owner has already solved.
    """
    owner_ids = select(Membership.user_id).where(
        Membership.company_id == company_id, Membership.role == "owner", Membership.status == "active"
    )
    await db.execute(delete(Notification).where(Notification.user_id.in_(owner_ids), Notification.type == "billing"))
    owner_emails = select(User.email).join(Membership, Membership.user_id == User.id).where(
        Membership.company_id == company_id,
        Membership.role == "owner",
        Membership.status == "active",
        User.is_active.is_(True),
    )
    await db.execute(
        update(EmailSend)
        .where(
            or_(
                EmailSend.company_id == company_id,
                and_(EmailSend.company_id.is_(None), EmailSend.recipient_email.in_(owner_emails)),
            ),
            EmailSend.source.in_([BILLING_REMINDER_SOURCE, BILLING_EXPIRY_SOURCE]),
            EmailSend.status == "queued",
        )
        .values(status="canceled", error="Plan paid before delivery")
    )


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
    ended = subscription.ends_at is not None and subscription.ends_at <= utc_now()
    if ended:
        grace_until = (subscription.ends_at + timedelta(hours=settings.billing_grace_hours)).date().isoformat()
        amount = period_total_label(current_plan.monthly_price, subscription.billing_cycle)
        title = f"Your {current_plan.name} plan ended {ends_label}"
        subject = f"Renew {current_plan.name} - grace ends {grace_until}"
        body_lines = [
            f"Your {current_plan.name} plan ended on {ends_label}. You're in a grace period until {grace_until}.",
            f"Renew {current_plan.name} for ${amount} ({cycle}) to keep your workspace running without interruption.",
        ]
    elif cancelling:
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
    warning = await _capacity_warning(db, company.id, current_plan if ended else next_plan)
    if warning:
        body_lines.append(warning)
    # Deep-link the owner straight into Billing with the right plan and cycle
    # selected, so the reminder is actionable instead of just informative. The
    # QR itself is minted on arrival (a KHQR expires long before the reminder
    # horizon), which is why the link carries intent rather than a payment.
    renew_plan_code = current_plan.code if ended else next_code
    renew_path = f"billing?renew={renew_plan_code}&cycle={subscription.billing_cycle}&pay=1"
    await _notify_owners(db, company.id, title, " ".join(body_lines[:2]), link=renew_path)

    owners = (
        await db.execute(
            select(User.email).join(Membership, Membership.user_id == User.id).where(
                Membership.company_id == company.id, Membership.role == "owner", Membership.status == "active"
            )
        )
    ).scalars().all()
    facts = [
        ["Plan", escape(next_plan.name)],
        ["Renewal", f"${escape(str(amount))} / {escape(cycle)}"],
        ["Grace ends" if ended else "Period ends", escape(grace_until if ended else ends_label)],
    ]
    paragraphs = "".join(f'<p style="margin:0 0 12px 0;">{escape(line)}</p>' for line in body_lines)
    for email in owners:
        renew_url = app_url(username_for(email, None), renew_path)
        html = transactional_email(
            heading=subject,
            preview=title,
            body=paragraphs + data_table(["", ""], facts, aligns=["left", "right"], show_header=False),
            badge="Billing",
            cta_label="Go to Billing & plans",
            cta_href=escape(renew_url),
            footnote=f'Billing &amp; plans: <a href="{escape(renew_url)}" style="color:#6957f5;">{escape(renew_url)}</a>',
        )
        queue_billing_notice(db, company_id=company.id, recipient_email=email, subject=subject, html=html, source=BILLING_REMINDER_SOURCE)
    db.add(BillingReminder(subscription_id=subscription.id, days_before=offset))


async def notify_expired_fallback(db: AsyncSession, company_id: UUID, *, plan_name: str, paused_stores: int, paused_members: int) -> None:
    """Tell owners their paid plan lapsed and what the Free fallback paused."""
    title = f"Your {plan_name} plan has expired"
    body = (
        f"Your workspace is now on the Free plan. "
        f"{paused_stores} store(s) and {paused_members} team member(s) are paused. "
        "Your data is safe - upgrade to restore them."
    )
    await _notify_owners(db, company_id, title, body, link="billing")
    owners = (
        await db.execute(
            select(User.email).join(Membership, Membership.user_id == User.id).where(
                Membership.company_id == company_id, Membership.role == "owner", Membership.status == "active"
            )
        )
    ).scalars().all()
    body_html = (
        '<p style="margin:0 0 12px 0;">Your workspace is now on the Free plan.</p>'
        f'<p style="margin:0 0 12px 0;">{paused_stores} store(s) and {paused_members} team member(s) are paused. '
        "Your data is safe &mdash; upgrade to restore them.</p>"
    )
    for email in owners:
        billing_url = app_url(username_for(email, None), "billing")
        html = transactional_email(
            heading=title,
            preview="Your paid plan has expired. Your workspace is on the Free plan.",
            body=body_html,
            badge="Billing",
            cta_label="Upgrade your plan",
            cta_href=escape(billing_url),
        )
        queue_billing_notice(db, company_id=company_id, recipient_email=email, subject=title, html=html, source=BILLING_EXPIRY_SOURCE)


async def run_reminder_job(db: AsyncSession) -> dict:
    """Send due reminders for active paid plans ending within the offsets."""
    now = utc_now()
    stats = {"reminders": 0}
    successor = aliased(Subscription)
    covered_by_next_period = ~select(successor.id).where(
        successor.company_id == Subscription.company_id,
        successor.id != Subscription.id,
        successor.status == "active",
        successor.ends_at.is_not(None),
        successor.starts_at <= Subscription.ends_at,
        successor.ends_at > Subscription.ends_at,
    ).exists()
    for offset in reminder_offsets():
        cutoff = now + timedelta(days=offset)
        due = (
            await db.execute(
                select(Subscription).where(
                    Subscription.status == "active",
                    Subscription.plan_code != FREE_PLAN_CODE,
                    Subscription.ends_at.is_not(None),
                    Subscription.ends_at > now,
                    Subscription.ends_at <= cutoff,
                    covered_by_next_period,
                    ~select(BillingReminder.id)
                    .where(BillingReminder.subscription_id == Subscription.id, BillingReminder.days_before == offset)
                    .exists(),
                )
            )
        ).scalars().all()
        for subscription in due:
            await _deliver_reminder(db, subscription, offset)
            stats["reminders"] += 1

    # Expiry-day / grace reminder: the period just ended but grace still covers it.
    grace_floor = now - timedelta(hours=settings.billing_grace_hours)
    in_grace = (
        await db.execute(
            select(Subscription).where(
                Subscription.status == "active",
                Subscription.plan_code != FREE_PLAN_CODE,
                Subscription.ends_at.is_not(None),
                Subscription.ends_at <= now,
                Subscription.ends_at > grace_floor,
                covered_by_next_period,
                ~select(BillingReminder.id)
                .where(BillingReminder.subscription_id == Subscription.id, BillingReminder.days_before == 0)
                .exists(),
            )
        )
    ).scalars().all()
    for subscription in in_grace:
        await _deliver_reminder(db, subscription, 0)
        stats["reminders"] += 1
    return stats
