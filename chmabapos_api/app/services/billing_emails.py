"""Owner-facing billing emails (payment receipts and failures).

Billing mail is transactional account mail: it is always sent (there is no
per-store toggle), queued through the ``email_sends`` outbox with source
``billing_receipt`` so a mail outage retries instead of losing the receipt, and
kept out of the marketing unsubscribe flow.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.email import app_url, username_for
from app.models import EmailSend, Membership, Plan, Subscription, User
from app.services.email_layout import data_table, transactional_email
from app.services.pricing import period_label, period_total_label
from app.services.sale_emails import format_money

BILLING_RECEIPT_SOURCE = "billing_receipt"
BILLING_FAILURE_SOURCE = "billing_failure"
BILLING_REMINDER_SOURCE = "billing_reminder"
BILLING_EXPIRY_SOURCE = "billing_expiry"
BILLING_PRICE_CHANGE_SOURCE = "billing_price_change"


async def _owner_emails(db: AsyncSession, company_id: UUID) -> list[str]:
    rows = (
        await db.execute(
            select(User.email)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.company_id == company_id,
                Membership.status == "active",
                Membership.role == "owner",
                User.is_active.is_(True),
            )
            .order_by(Membership.created_at)
        )
    ).scalars().all()
    return [email for email in rows if email]


def _period(period_end: datetime | None) -> str:
    return period_end.strftime("%d %b %Y") if period_end else "—"


async def queue_billing_receipt_email(
    db: AsyncSession,
    *,
    company_id: UUID,
    plan_code: str,
    amount,
    currency_code: str,
    receipt_number: str,
    period_end: datetime | None,
    paid_at: datetime,
) -> int:
    """Queue a payment receipt to every owner. Returns the number queued."""
    plan = await db.get(Plan, plan_code)
    plan_name = plan.name if plan is not None else plan_code
    valid_until = _period(period_end)
    body = (
        f'<p style="margin:0 0 4px 0;">We received your payment. Your '
        f"<strong>{escape(plan_name)}</strong> plan is active through {escape(valid_until)}.</p>"
        + data_table(
            ["Receipt", "Plan", "Amount", "Paid", "Valid until"],
            [
                [
                    escape(receipt_number),
                    escape(plan_name),
                    escape(format_money(amount, currency_code)),
                    escape(paid_at.strftime("%d %b %Y")),
                    escape(valid_until),
                ]
            ],
            aligns=["left", "left", "right", "left", "left"],
        )
        + '<p style="margin:18px 0 0 0;">Find this and past receipts under Billing &amp; plans in your workspace.</p>'
    )
    html = transactional_email(
        heading="Payment received",
        preview=f"{format_money(amount, currency_code)} · {plan_name}",
        body=body,
        badge="Billing",
    )
    queued = 0
    for email in await _owner_emails(db, company_id):
        db.add(
            EmailSend(
                recipient_email=email,
                subject=f"Payment received · {receipt_number}",
                body_html=html,
                status="queued",
                source=BILLING_RECEIPT_SOURCE,
            )
        )
        queued += 1
    return queued


async def queue_billing_failure_email(
    db: AsyncSession,
    *,
    company_id: UUID,
    plan_code: str,
    amount,
    currency_code: str,
    reason: str = "failed",
) -> int:
    """Queue a "payment did not go through" email to every owner.

    Called when a provider reports a failed or expired plan payment, so the
    owner can retry before their paid period lapses.
    """
    plan = await db.get(Plan, plan_code)
    plan_name = plan.name if plan is not None else plan_code
    lead = "expired before it was paid" if reason == "expired" else "did not go through"
    body = (
        f'<p style="margin:0 0 4px 0;">Your payment for the <strong>{escape(plan_name)}</strong> plan '
        f"{lead}. Your workspace keeps working until your current period ends.</p>"
        + data_table(
            ["Plan", "Amount", "Status"],
            [[escape(plan_name), escape(format_money(amount, currency_code)), escape(reason.title())]],
            aligns=["left", "right", "left"],
        )
        + '<p style="margin:18px 0 0 0;">Open Billing &amp; plans in your workspace to try the payment again.</p>'
    )
    html = transactional_email(
        heading="Payment did not go through",
        preview=f"Retry your {escape(plan_name)} payment.",
        body=body,
        badge="Billing",
    )
    queued = 0
    for email in await _owner_emails(db, company_id):
        db.add(
            EmailSend(
                recipient_email=email,
                subject=f"Payment did not go through · {plan_name}",
                body_html=html,
                status="queued",
                source=BILLING_FAILURE_SOURCE,
            )
        )
        queued += 1
    return queued


def queue_billing_notice(
    db: AsyncSession,
    *,
    company_id: UUID,
    recipient_email: str,
    subject: str,
    html: str,
    source: str,
) -> None:
    """Queue one transactional billing notice to the outbox.

    Renewal and expiry nudges are sent through ``email_sends`` rather than
    inline: a mail outage must retry the reminder instead of dropping it, and the
    row is the record that it was attempted. ``source`` is one of the
    ``BILLING_*_SOURCE`` constants so the drain treats it as transactional.
    """
    db.add(EmailSend(company_id=company_id, recipient_email=recipient_email, subject=subject, body_html=html, status="queued", source=source))


async def queue_plan_price_change_notices(
    db: AsyncSession,
    *,
    plan: Plan,
    old_price: Decimal,
    new_price: Decimal,
) -> int:
    """Tell in-force subscribers that their next renewal costs more/less.

    The paid period they already hold is untouched (``plan_terms`` keeps the
    old price), but the next renewal re-snapshots the live plan. Sending this
    when an admin edits the catalog closes the surprise gap between the price on
    the billing page and the price in the renewal reminder. Only companies with
    paid time still ahead of them are notified, one mail per owner.
    """
    if plan.code == "free" or Decimal(str(old_price)) == Decimal(str(new_price)):
        return 0
    now = datetime.now(timezone.utc)
    rows = (
        await db.execute(
            select(Subscription)
            .where(
                Subscription.plan_code == plan.code,
                Subscription.status == "active",
                Subscription.ends_at.is_not(None),
                Subscription.ends_at > now,
            )
            .order_by(Subscription.ends_at.desc())
        )
    ).scalars().all()
    # A same-plan stacked renewal leaves several active rows per company; the
    # latest one is the first row and describes when the next charge lands.
    by_company: dict[UUID, Subscription] = {}
    for subscription in rows:
        by_company.setdefault(subscription.company_id, subscription)

    queued = 0
    for company_id, subscription in by_company.items():
        cycle = subscription.billing_cycle
        cycle_label = period_label(cycle)
        old_total = period_total_label(old_price, cycle)
        new_total = period_total_label(new_price, cycle)
        if Decimal(old_total) == Decimal(new_total):
            continue
        ends_label = subscription.ends_at.strftime("%d %b %Y") if subscription.ends_at else "your period end"
        subject = f"Your {plan.name} renewal price changes to ${Decimal(str(new_price)):.2f}/month"
        body = (
            f'<p style="margin:0 0 12px 0;">The price of the <strong>{escape(plan.name)}</strong> plan '
            f"is changing from ${old_total} to ${new_total} ({escape(cycle_label)}).</p>"
            f'<p style="margin:0 0 12px 0;">Nothing changes before {escape(ends_label)}: your current period '
            f"keeps the price you already paid. When it ends, your renewal is ${new_total} ({escape(cycle_label)}).</p>"
            + data_table(
                ["", ""],
                [
                    ["Plan", escape(plan.name)],
                    ["Current period", f"${old_total} / {escape(cycle_label)}"],
                    ["Renewal", f"${new_total} / {escape(cycle_label)}"],
                    ["Renews after", escape(ends_label)],
                ],
                aligns=["left", "right"],
                show_header=False,
            )
            + '<p style="margin:18px 0 0 0;">Review the plan and its limits under Billing &amp; plans in your workspace.</p>'
        )
        for email in await _owner_emails(db, company_id):
            billing_url = app_url(username_for(email, None), "billing")
            html = transactional_email(
                heading=f"{plan.name} renewal price is changing",
                preview=f"${old_total} → ${new_total} {cycle_label} from {ends_label}.",
                body=body,
                badge="Billing",
                cta_label="Review Billing & plans",
                cta_href=escape(billing_url),
                footnote=f'Billing &amp; plans: <a href="{escape(billing_url)}" style="color:#6957f5;">{escape(billing_url)}</a>',
            )
            queue_billing_notice(
                db,
                company_id=company_id,
                recipient_email=email,
                subject=subject,
                html=html,
                source=BILLING_PRICE_CHANGE_SOURCE,
            )
            queued += 1
    return queued
