"""Owner-facing billing emails (payment receipts and failures).

Billing mail is transactional account mail: it is always sent (there is no
per-store toggle), queued through the ``email_sends`` outbox with source
``billing_receipt`` so a mail outage retries instead of losing the receipt, and
kept out of the marketing unsubscribe flow.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailSend, Membership, Plan, User
from app.services.email_layout import data_table, transactional_email
from app.services.sale_emails import format_money

BILLING_RECEIPT_SOURCE = "billing_receipt"


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
