"""Automatic operational emails for a store.

Every message here is opt-in under ``Store.preferences['notifications']`` (the
same toggles shown in Settings → Notifications) and off by default:

* ``daily_summary``   — one end-of-day summary per store per day.
* ``low_stock_alerts``— one low-stock digest per store per day when items are low.
* ``refund_activity`` — a note whenever a refund is recorded.
* ``shift_reminders`` — a note when a shift has been open too long.
* ``team_activity``   — a note when the team changes.

Time-based messages are produced by :func:`run_store_notifications` on a
schedule; event messages are queued at the moment the event happens. Everything
is written to the ``email_sends`` outbox (source ``store_note``) and delivered
by the mailing worker, so a mail outage can never block a sale or a settings
change. The per-store ``notification_state`` marker is what keeps a daily
message from being sent twice.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from html import escape
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailSend, Membership, Order, Refund, Shift, Store, User
from app.services.email_layout import data_table, transactional_email
from app.services.inventory import low_stock_items
from app.services.sale_emails import format_money, format_quantity, notification_prefs, sale_alert_frequency

# Source tag for these outbox rows. ``mailing`` treats it as transactional
# (no marketing unsubscribe header, not suppressed by the unsubscribe list).
STORE_NOTE_SOURCE = "store_note"

SUMMARY_HOUR = 20
LOW_STOCK_HOUR = 8
SHIFT_REMINDER_HOURS = 12

TIME_BASED_KEYS = ("daily_summary", "low_stock_alerts", "shift_reminders")


def _tz(name: str | None):
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name or "Asia/Phnom_Penh")
    except Exception:
        # Asia/Phnom_Penh has no DST; this also keeps Windows hosts working.
        return timezone(timedelta(hours=7))


def is_enabled(store: Store, key: str) -> bool:
    return bool(notification_prefs(store).get(key))


def _state(store: Store) -> dict:
    value = (store.preferences or {}).get("notification_state")
    return dict(value) if isinstance(value, dict) else {}


def _save_state(store: Store, state: dict) -> None:
    prefs = dict(store.preferences or {})
    prefs["notification_state"] = state
    store.preferences = prefs


async def owner_emails(db: AsyncSession, company_id: UUID) -> list[str]:
    rows = (
        await db.execute(
            select(User.email)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.company_id == company_id, Membership.status == "active", Membership.role == "owner", User.is_active.is_(True))
            .order_by(Membership.created_at)
        )
    ).scalars().all()
    return [email for email in rows if email]


async def queue_owner_note(db: AsyncSession, store: Store, key: str, subject: str, body: str) -> int:
    """Queue one email to every owner, unless the store has turned ``key`` off."""
    if not is_enabled(store, key):
        return 0
    queued = 0
    for email in await owner_emails(db, store.company_id):
        db.add(EmailSend(recipient_email=email, subject=subject, body_html=body, status="queued", source=STORE_NOTE_SOURCE))
        queued += 1
    return queued


async def daily_summary_body(db: AsyncSession, store: Store, day) -> str:
    start_at = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    count, gross = (
        await db.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0)).where(
                Order.store_id == store.id, Order.status == "paid", Order.created_at >= start_at, Order.created_at < end_at
            )
        )
    ).one()
    refund_total = (
        await db.execute(
            select(func.coalesce(func.sum(Refund.total), 0)).where(Refund.store_id == store.id, Refund.created_at >= start_at, Refund.created_at < end_at)
        )
    ).scalar_one()
    body = (
        f'<p style="margin:0 0 4px 0;">Here is how <strong>{escape(store.name)}</strong> performed on '
        f'{day.strftime("%A, %d %B %Y")}.</p>'
        + data_table(
            ["Orders", "Gross sales", "Refunds"],
            [
                [
                    f"{int(count):,}",
                    escape(format_money(gross, store.currency_code)),
                    escape(format_money(refund_total, store.currency_code)),
                ]
            ],
            aligns=["center", "center", "center"],
        )
    )
    return transactional_email(
        heading="Daily summary",
        preview=f"{int(count):,} orders · {format_money(gross, store.currency_code)} at {escape(store.name)}",
        body=body,
        badge="Daily summary",
    )


async def low_stock_body(db: AsyncSession, store: Store) -> tuple[str, str] | None:
    rows = await low_stock_items(db, store_id=store.id)
    if not rows:
        return None
    count = len(rows)
    out_of_stock = sum(1 for item in rows if Decimal(str(item["on_hand"])) <= 0)
    intro = (
        f'<p style="margin:0 0 4px 0;">{count} item{"s" if count != 1 else ""} at '
        f'<strong>{escape(store.name)}</strong> {"are" if count != 1 else "is"} at or below the reorder point.'
    )
    if out_of_stock:
        intro += f' {out_of_stock} {"are" if out_of_stock != 1 else "is"} already out of stock.'
    intro += "</p>"
    items = []
    for item in rows:
        label = escape(item["name"])
        if item["variant_name"]:
            label = f'{label} <span style="color:#92939d;">&middot; {escape(item["variant_name"])}</span>'
        on_hand = item["on_hand"]
        quantity = format_quantity(on_hand)
        if Decimal(str(on_hand)) <= 0:
            quantity = f'<strong style="color:#b45309;">{quantity}</strong>'
        reorder = item["reorder_point"]
        items.append([label, quantity, format_quantity(reorder) if reorder is not None else "&mdash;"])
    body = intro + data_table(["Product", "On hand", "Reorder at"], items, aligns=["left", "right", "right"])
    return (
        f"Low stock alert · {store.name}",
        transactional_email(
            heading="Low stock alert",
            preview=f'{count} item{"s" if count != 1 else ""} need restocking at {escape(store.name)}.',
            body=body,
            badge="Inventory",
            footnote="Update your reorder points or receive stock so these items do not sell out.",
        ),
    )


async def sales_digest_body(db: AsyncSession, store: Store, day) -> str:
    """One message listing the day's sales, for the ``daily`` alert frequency."""
    start_at = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    orders = (
        await db.execute(
            select(Order)
            .where(Order.store_id == store.id, Order.status == "paid", Order.created_at >= start_at, Order.created_at < end_at)
            .order_by(Order.created_at)
        )
    ).scalars().all()
    gross = sum((order.total for order in orders), Decimal("0.00"))
    body = (
        f'<p style="margin:0 0 4px 0;">Sales for <strong>{escape(store.name)}</strong> on '
        f'{day.strftime("%A, %d %B %Y")}.</p>'
        + data_table(
            ["Orders", "Gross sales"],
            [[f"{len(orders):,}", escape(format_money(gross, store.currency_code))]],
            aligns=["center", "center"],
        )
    )
    if orders:
        body += data_table(
            ["Order", "Time", "Total"],
            [
                [
                    escape(order.order_number),
                    escape((order.paid_at or order.created_at).strftime("%H:%M")),
                    escape(format_money(order.total, order.currency_code)),
                ]
                for order in orders
            ],
            aligns=["left", "center", "right"],
        )
    return transactional_email(
        heading="Sales today",
        preview=f"{len(orders):,} orders · {format_money(gross, store.currency_code)} at {escape(store.name)}",
        body=body,
        badge="Sales",
    )


async def queue_refund_note(db: AsyncSession, store: Store, *, order_number: str, total, currency_code: str, method: str, actor: str) -> int:
    subject = f"Refund · {store.name} · {format_money(total, currency_code)}"
    body = (
        f'<p style="margin:0 0 4px 0;">A refund was recorded at <strong>{escape(store.name)}</strong>.</p>'
        + data_table(
            ["Order", "Amount", "Method", "Recorded by"],
            [
                [
                    escape(order_number),
                    escape(format_money(total, currency_code)),
                    escape(method.title()),
                    escape(actor),
                ]
            ],
            aligns=["left", "right", "left", "left"],
        )
    )
    return await queue_owner_note(
        db,
        store,
        "refund_activity",
        subject,
        transactional_email(
            heading="Refund recorded",
            preview=f"{format_money(total, currency_code)} refunded at {escape(store.name)}.",
            body=body,
            badge="Refund",
        ),
    )


async def queue_team_activity(db: AsyncSession, company_id: UUID, *, title: str, detail: str) -> int:
    """Team changes are company-wide, so send if any active store opted in."""
    stores = (
        await db.execute(select(Store).where(Store.company_id == company_id, Store.is_active.is_(True)).order_by(Store.created_at))
    ).scalars().all()
    store = next((candidate for candidate in stores if is_enabled(candidate, "team_activity")), None)
    if store is None:
        return 0
    body = transactional_email(
        heading=escape(title),
        preview=escape(detail),
        body=f'<p style="margin:0;">{escape(detail)}</p>',
        badge="Team",
    )
    return await queue_owner_note(db, store, "team_activity", title, body)


async def run_store_notifications(db: AsyncSession, *, now: datetime | None = None) -> dict:
    """Queue the time-based owner notes that are due right now.

    Idempotent per local day (daily summary, low stock) and per open shift, so
    running it on a short interval cannot double-send.
    """
    now = now or datetime.now(timezone.utc)
    stats = {"stores": 0, "summaries": 0, "low_stock": 0, "shift_reminders": 0, "sale_digests": 0}
    stores = (await db.execute(select(Store).where(Store.is_active.is_(True)))).scalars().all()
    for store in stores:
        prefs = notification_prefs(store)
        digest_due = bool(prefs.get("sale_alert")) and sale_alert_frequency(prefs) == "daily"
        if not any(prefs.get(key) for key in TIME_BASED_KEYS) and not digest_due:
            continue
        stats["stores"] += 1
        local = now.astimezone(_tz(store.timezone))
        today = local.date().isoformat()
        state = _state(store)
        changed = False

        if digest_due and local.hour >= SUMMARY_HOUR and state.get("sale_digest") != today:
            body = await sales_digest_body(db, store, local.date())
            stats["sale_digests"] += await queue_owner_note(db, store, "sale_alert", f"Sales today · {store.name}", body)
            state["sale_digest"] = today
            changed = True

        if prefs.get("daily_summary") and local.hour >= SUMMARY_HOUR and state.get("daily_summary") != today:
            body = await daily_summary_body(db, store, local.date())
            stats["summaries"] += await queue_owner_note(db, store, "daily_summary", f"Daily summary · {store.name}", body)
            state["daily_summary"] = today
            changed = True

        if prefs.get("low_stock_alerts") and local.hour >= LOW_STOCK_HOUR and state.get("low_stock") != today:
            note = await low_stock_body(db, store)
            if note:
                stats["low_stock"] += await queue_owner_note(db, store, "low_stock_alerts", note[0], note[1])
            state["low_stock"] = today
            changed = True

        if prefs.get("shift_reminders"):
            cutoff = now - timedelta(hours=SHIFT_REMINDER_HOURS)
            open_shifts = (
                await db.execute(select(Shift).where(Shift.store_id == store.id, Shift.status == "open", Shift.opened_at <= cutoff))
            ).scalars().all()
            current = {str(shift.id): shift for shift in open_shifts}
            reminded = {key: value for key, value in (state.get("shifts") or {}).items() if key in current}
            for shift_id, shift in current.items():
                if shift_id in reminded:
                    continue
                opened = shift.opened_at.astimezone(local.tzinfo).strftime("%Y-%m-%d %H:%M") if shift.opened_at else "earlier"
                body = (
                    f'<p style="margin:0 0 4px 0;">A shift at <strong>{escape(store.name)}</strong> has been open for more '
                    f"than {SHIFT_REMINDER_HOURS} hours. It may need closing.</p>"
                    + data_table(["Opened", "Status"], [[escape(opened), "Still open"]], aligns=["left", "right"])
                )
                stats["shift_reminders"] += await queue_owner_note(
                    db,
                    store,
                    "shift_reminders",
                    f"Shift still open · {store.name}",
                    transactional_email(
                        heading="Shift still open",
                        preview=f"A shift at {escape(store.name)} has been open for over {SHIFT_REMINDER_HOURS} hours.",
                        body=body,
                        badge="Shift",
                    ),
                )
                reminded[shift_id] = now.isoformat()
            state["shifts"] = reminded
            changed = True

        if changed:
            _save_state(store, state)

    await db.commit()
    return stats
