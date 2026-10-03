"""Automatic emails for a completed sale: an owner alert and a customer receipt.

Neither message is delivered from inside the sale transaction. Instead one row
per recipient is written to the ``email_sends`` outbox (sources ``sale_alert``
and ``receipt``) and the mailing queue worker delivers it with retries, so a
slow or broken mail provider can never delay a charge or roll back a sale.

Both messages are opt-in per store under ``Store.preferences['notifications']``
and are off by default:

* ``sale_alert`` — email the store owners that a sale just happened.
* ``customer_receipt`` — email the customer their receipt. This additionally
  requires the paid ``email_receipts`` capability and a customer email.

Keeping the decision and the copy here (rather than in the order or mail
services) means the order flow only has to call :func:`queue_sale_emails`.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import load_entitlement
from app.models import Company, EmailSend, Membership, Order, Store, User

SALE_ALERT_SOURCE = "sale_alert"
RECEIPT_SOURCE = "receipt"
# Queue rows from these sources are transactional: they ignore the marketing
# unsubscribe list and are sent without a ``List-Unsubscribe`` header.
# ``store_note`` is defined in ``store_notifications.STORE_NOTE_SOURCE``.
TRANSACTIONAL_SOURCES = frozenset({SALE_ALERT_SOURCE, RECEIPT_SOURCE, "store_note"})


def format_money(value, code: str) -> str:
    """Format an amount the same way the POS does (no currency symbols)."""
    amount = Decimal(str(value))
    if code == "KHR":
        return f"KHR {int(amount.quantize(Decimal('1'))):,}"
    return f"{code} {amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def notification_prefs(store: Store) -> dict:
    """The store's notification toggles, or an empty dict when unset."""
    prefs = dict(store.preferences or {})
    value = prefs.get("notifications")
    return value if isinstance(value, dict) else {}


def _customer_label(order: Order) -> str | None:
    if order.customer is not None and order.customer.name:
        return order.customer.name
    return order.customer_name or None


def _payment_lines(order: Order) -> list[str]:
    return [f"  {tender.method.title()} {format_money(tender.amount, tender.currency_code)}" for tender in order.tenders if tender.kind == "payment"]


def sale_alert_body(order: Order, store: Store) -> tuple[str, str]:
    """Subject and body for the owner "a sale just happened" alert."""
    code = order.currency_code
    when = order.paid_at or order.created_at
    lines = [
        f"New sale at {store.name}",
        "",
        f"Order: {order.order_number}",
        f"When: {when.strftime('%Y-%m-%d %H:%M')}",
        f"Customer: {_customer_label(order) or 'Walk-in'}",
        "",
        "Items:",
        *(f"  {item.quantity} x {item.product_name} @ {format_money(item.unit_price, code)} = {format_money(item.line_total, code)}" for item in order.items),
        "",
        f"Subtotal: {format_money(order.subtotal, code)}",
        *([f"Discount: -{format_money(order.discount, code)}"] if order.discount else []),
        f"Tax: {format_money(order.tax, code)}",
        f"Total: {format_money(order.total, code)}",
    ]
    payments = _payment_lines(order)
    if payments:
        lines += ["", "Paid by:", *payments]
    lines += ["", "Sent by Chmaba"]
    return f"New sale · {store.name} · {format_money(order.total, code)}", "\n".join(lines)


def receipt_body(order: Order, store: Store, company_name: str) -> tuple[str, str]:
    """Subject and body for a customer receipt (also used by the manual send)."""
    code = order.currency_code
    lines = [company_name, store.name]
    if store.address:
        lines.append(store.address)
    lines += [
        "",
        f"Receipt {order.order_number}",
        f"Date: {order.created_at.strftime('%Y-%m-%d %H:%M')}",
    ]
    customer = _customer_label(order)
    if customer:
        lines.append(f"Customer: {customer}")
    lines += [
        "",
        "Items:",
        *(f"  {item.quantity} x {item.product_name} @ {format_money(item.unit_price, code)} = {format_money(item.line_total, code)}" for item in order.items),
        "",
        f"Subtotal: {format_money(order.subtotal, code)}",
        *([f"Discount: -{format_money(order.discount, code)}"] if order.discount else []),
        *([f"Tip: {format_money(order.tip, code)}"] if order.tip else []),
        f"Tax: {format_money(order.tax, code)}",
        f"Total: {format_money(order.total, code)}",
    ]
    payments = [f"  {tender.method.title()} {format_money(tender.amount, tender.currency_code)} ({tender.currency_code})" for tender in order.tenders if tender.kind == "payment"]
    change = next((tender for tender in order.tenders if tender.kind == "change"), None)
    if payments:
        lines += ["", "Paid by:", *payments]
    if change:
        lines.append(f"Change: {format_money(change.amount, change.currency_code)}")
    lines += ["", "Thank you for shopping with us!", "Sent by Chmaba"]
    return f"Your receipt for {order.order_number}", "\n".join(lines)


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


async def _has_email_receipts(db: AsyncSession, company_id: UUID) -> bool:
    try:
        entitlement = await load_entitlement(db, company_id)
    except Exception:
        return False
    return bool(entitlement.plan and entitlement.plan.capabilities.get("email_receipts"))


async def _already_queued(db: AsyncSession, source: str, recipient: str, subject: str) -> bool:
    """Cheap dedupe so a retried completion cannot enqueue the same message twice."""
    existing = await db.scalar(
        select(EmailSend.id).where(
            EmailSend.source == source,
            EmailSend.recipient_email == recipient,
            EmailSend.subject == subject,
        )
    )
    return existing is not None


async def queue_sale_emails(db: AsyncSession, order: Order, store: Store) -> dict:
    """Queue the owner alert and/or customer receipt for a just-completed order.

    Never raises: a failure here must not affect the sale, so the caller does
    not have to guard it (though :func:`complete_order` still does).
    """
    prefs = notification_prefs(store)
    queued = {"owner": 0, "customer": 0}
    company_id = store.company_id

    if prefs.get("sale_alert"):
        subject, body = sale_alert_body(order, store)
        for email in await _owner_emails(db, company_id):
            if await _already_queued(db, SALE_ALERT_SOURCE, email, subject):
                continue
            db.add(EmailSend(recipient_email=email, subject=subject, body_html=body, status="queued", source=SALE_ALERT_SOURCE))
            queued["owner"] += 1

    if prefs.get("customer_receipt") and order.customer is not None and order.customer.email:
        if await _has_email_receipts(db, company_id):
            company_name = (await db.execute(select(Company.name).where(Company.id == company_id))).scalar_one_or_none() or store.name
            subject, body = receipt_body(order, store, company_name)
            recipient = order.customer.email
            if not await _already_queued(db, RECEIPT_SOURCE, recipient, subject):
                db.add(EmailSend(recipient_email=recipient, subject=subject, body_html=body, status="queued", source=RECEIPT_SOURCE))
                queued["customer"] += 1

    return queued
