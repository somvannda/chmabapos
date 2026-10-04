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
from html import escape
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import load_entitlement
from app.models import Company, Customer, EmailSend, Membership, Order, Store, User
from app.services.email_layout import data_table, totals_table, transactional_email

SALE_ALERT_SOURCE = "sale_alert"
RECEIPT_SOURCE = "receipt"
# Queue rows from these sources are transactional: they ignore the marketing
# unsubscribe list and are sent without a ``List-Unsubscribe`` header.
# ``store_note`` is defined in ``store_notifications.STORE_NOTE_SOURCE``.
REFUND_SOURCE = "refund_confirmation"
ONLINE_ORDER_ACK_SOURCE = "online_order_ack"
TRANSACTIONAL_SOURCES = frozenset(
    {
        SALE_ALERT_SOURCE,
        RECEIPT_SOURCE,
        REFUND_SOURCE,
        ONLINE_ORDER_ACK_SOURCE,
        "store_note",
        "billing_receipt",
        "billing_failure",
    }
)


def format_money(value, code: str) -> str:
    """Format an amount the same way the POS does (no currency symbols)."""
    amount = Decimal(str(value))
    if code == "KHR":
        return f"KHR {int(amount.quantize(Decimal('1'))):,}"
    return f"{code} {amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def format_quantity(value) -> str:
    """Format a quantity without trailing Decimal zeros (``0.000`` -> ``0``)."""
    amount = Decimal(str(value))
    if amount == amount.to_integral_value():
        return f"{int(amount):,}"
    return format(amount.normalize(), "f").rstrip("0").rstrip(".")


def notification_prefs(store: Store) -> dict:
    """The store's notification toggles, or an empty dict when unset."""
    prefs = dict(store.preferences or {})
    value = prefs.get("notifications")
    return value if isinstance(value, dict) else {}


def sale_alert_frequency(prefs: dict) -> str:
    """``every_sale`` (default) or ``daily`` for the owner sale alert."""
    value = str(prefs.get("sale_alert_frequency") or "every_sale").strip().lower()
    return "daily" if value == "daily" else "every_sale"


def _customer_label(order: Order) -> str | None:
    if order.customer is not None and order.customer.name:
        return order.customer.name
    return order.customer_name or None


def _item_rows(order: Order, code: str) -> list[list[str]]:
    return [
        [
            escape(item.product_name),
            f"{format_quantity(item.quantity)} &times;",
            escape(format_money(item.unit_price, code)),
            escape(format_money(item.line_total, code)),
        ]
        for item in order.items
    ]


def _payment_rows(order: Order, *, with_currency: bool = False) -> list[list[str]]:
    rows = []
    for tender in order.tenders:
        if tender.kind != "payment":
            continue
        amount = format_money(tender.amount, tender.currency_code)
        if with_currency:
            amount = f"{amount} ({tender.currency_code})"
        rows.append([escape(tender.method.title()), escape(amount)])
    return rows


def _totals(order: Order, code: str, *, include_tip: bool = False) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = [("Subtotal", escape(format_money(order.subtotal, code)))]
    if order.discount:
        rows.append(("Discount", escape(f"-{format_money(order.discount, code)}")))
    if include_tip and order.tip:
        rows.append(("Tip", escape(format_money(order.tip, code))))
    rows.append(("Tax", escape(format_money(order.tax, code))))
    rows.append(("Total", escape(format_money(order.total, code))))
    return rows


def sale_alert_body(order: Order, store: Store) -> tuple[str, str]:
    """Subject and body for the owner "a sale just happened" alert."""
    code = order.currency_code
    when = order.paid_at or order.created_at
    body = (
        f'<p style="margin:0 0 15px 0;">A new sale was completed at <strong>{escape(store.name)}</strong>.</p>'
        + data_table(
            ["Order", "When", "Customer"],
            [[escape(order.order_number), escape(when.strftime("%Y-%m-%d %H:%M")), escape(_customer_label(order) or "Walk-in")]],
        )
        + data_table(
            ["Item", "Qty", "Price", "Amount"],
            _item_rows(order, code),
            aligns=["left", "right", "right", "right"],
        )
        + totals_table(_totals(order, code))
    )
    payments = _payment_rows(order)
    if payments:
        body += '<p style="margin:20px 0 6px 0;font-weight:700;color:#202128;">Paid by</p>'
        body += data_table(["Method", "Amount"], payments, aligns=["left", "right"])
    return (
        f"New sale · {store.name} · {format_money(order.total, code)}",
        transactional_email(
            heading="New sale",
            preview=f"{format_money(order.total, code)} · {order.order_number} at {escape(store.name)}",
            body=body,
            badge="Sale",
        ),
    )


def receipt_body(order: Order, store: Store, company_name: str) -> tuple[str, str]:
    """Subject and body for a customer receipt (also used by the manual send)."""
    code = order.currency_code
    identity = f"<strong>{escape(company_name or store.name)}</strong>"
    if company_name and company_name != store.name:
        identity += f"<br />{escape(store.name)}"
    if store.address:
        identity += f'<br /><span style="color:#92939d;">{escape(store.address)}</span>'
    meta = [
        ["Receipt", escape(order.order_number)],
        ["Date", escape(order.created_at.strftime("%Y-%m-%d %H:%M"))],
    ]
    customer = _customer_label(order)
    if customer:
        meta.append(["Customer", escape(customer)])
    body = (
        f'<p style="margin:0 0 15px 0;">{identity}</p>'
        + data_table(["", ""], meta, aligns=["left", "right"], show_header=False)
        + data_table(
            ["Item", "Qty", "Price", "Amount"],
            _item_rows(order, code),
            aligns=["left", "right", "right", "right"],
        )
        + totals_table(_totals(order, code, include_tip=True))
    )
    payments = _payment_rows(order, with_currency=True)
    if payments:
        body += '<p style="margin:20px 0 6px 0;font-weight:700;color:#202128;">Paid by</p>'
        body += data_table(["Method", "Amount"], payments, aligns=["left", "right"])
    change = next((tender for tender in order.tenders if tender.kind == "change"), None)
    if change:
        body += totals_table([("Change", escape(format_money(change.amount, change.currency_code)))])
    return (
        f"Your receipt for {order.order_number}",
        transactional_email(
            heading=f"Receipt {order.order_number}",
            preview=f"Thank you for shopping at {escape(store.name)}.",
            body=body,
            badge="Receipt",
            footnote="Thank you for shopping with us!",
        ),
    )


async def queue_refund_confirmation(
    db: AsyncSession,
    order: Order,
    store: Store,
    *,
    company_name: str,
    amount,
    method: str,
) -> int:
    """Email the buyer when part or all of an order is refunded.

    Gated on the same paid ``email_receipts`` capability and customer email as
    the receipt. Returns the number of emails queued (0 or 1).
    """
    customer = order.customer
    if customer is None and order.customer_id is not None:
        customer = await db.get(Customer, order.customer_id)
    if customer is None or not customer.email:
        return 0
    if not await _has_email_receipts(db, store.company_id):
        return 0
    code = order.currency_code
    body = (
        f'<p style="margin:0 0 4px 0;">We processed a refund for your order at '
        f"<strong>{escape(company_name or store.name)}</strong>.</p>"
        + data_table(
            ["Order", "Refund", "Method"],
            [[escape(order.order_number), escape(format_money(amount, code)), escape(method.title())]],
            aligns=["left", "right", "left"],
        )
        + '<p style="margin:18px 0 0 0;">Depending on your bank or card issuer, it may take a few '
        "business days to appear.</p>"
    )
    html = transactional_email(
        heading="Refund processed",
        preview=f"{format_money(amount, code)} refunded for {order.order_number}",
        body=body,
        badge="Receipt",
        footnote="Thank you for shopping with us!",
    )
    db.add(
        EmailSend(
            recipient_email=customer.email,
            subject=f"Refund processed · {order.order_number}",
            body_html=html,
            status="queued",
            source=REFUND_SOURCE,
        )
    )
    return 1


async def queue_online_order_acknowledgement(
    db: AsyncSession,
    store: Store,
    *,
    recipient: str,
    customer_name: str | None,
    label: str | None,
    lines: list[dict],
) -> int:
    """Email the customer that their online/QR order was received.

    The address is provided by the customer on the public form and used only for
    this acknowledgement.
    """
    code = store.currency_code
    rows: list[list[str]] = []
    total = Decimal("0.00")
    for line in lines:
        amount = Decimal(str(line.get("line_total") or 0))
        total += amount
        name = escape(str(line.get("product_name") or "Item"))
        variant = line.get("variant_name")
        if variant:
            name = f'{name} <span style="color:#92939d;">&middot; {escape(str(variant))}</span>'
        rows.append(
            [
                name,
                format_quantity(Decimal(str(line.get("quantity") or 0))),
                escape(format_money(amount, code)),
            ]
        )
    greeting = f"Hi {escape(customer_name)}, " if customer_name else ""
    where = f" for <strong>{escape(label)}</strong>" if label else ""
    body = (
        f'<p style="margin:0 0 4px 0;">{greeting}we have your order at '
        f"<strong>{escape(store.name)}</strong>{where}.</p>"
        + data_table(["Item", "Qty", "Amount"], rows, aligns=["left", "right", "right"])
        + totals_table([("Total", escape(format_money(total, code)))])
        + '<p style="margin:18px 0 0 0;">Please pay at the counter. We will have it ready shortly.</p>'
    )
    html = transactional_email(
        heading="We have your order",
        preview=f"{len(lines)} item(s) · {format_money(total, code)} at {escape(store.name)}",
        body=body,
        badge="Order",
    )
    db.add(
        EmailSend(
            recipient_email=recipient,
            subject=f"Order received · {store.name}",
            body_html=html,
            status="queued",
            source=ONLINE_ORDER_ACK_SOURCE,
        )
    )
    return 1


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

    if prefs.get("sale_alert") and sale_alert_frequency(prefs) != "daily":
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
