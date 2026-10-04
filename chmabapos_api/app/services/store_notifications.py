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

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html import escape
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailSend, HeldOrder, Membership, Notification, Order, Refund, Shift, Store, User
from app.services.email_layout import data_table, totals_table, transactional_email
from app.services.inventory import low_stock_items
from app.services.sale_emails import format_money, format_quantity, notification_prefs, sale_alert_frequency

# Source tag for these outbox rows. ``mailing`` treats it as transactional
# (no marketing unsubscribe header, not suppressed by the unsubscribe list).
STORE_NOTE_SOURCE = "store_note"

SUMMARY_HOUR = 20
LOW_STOCK_HOUR = 8
SHIFT_REMINDER_HOURS = 12

TIME_BASED_KEYS = ("daily_summary", "low_stock_alerts", "shift_reminders", "weekly_report", "monthly_report", "operations_digest")
WEEKLY_REPORT_WEEKDAY = 0  # Monday (Python weekday numbering).

# In-app events that had no email of their own; folded into one daily digest.
DIGEST_TYPES = ("approval_request", "discount_review", "refund_review", "stock_transfer")


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


async def weekly_summary_body(db: AsyncSession, store: Store, end_day) -> str:
    """One message summarizing the seven days ending ``end_day`` (inclusive)."""
    start_day = end_day - timedelta(days=6)
    start_at = datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc)
    end_at = datetime.combine(end_day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    code = store.currency_code
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
    daily_rows = (
        await db.execute(
            select(func.date(Order.created_at), func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
            .where(Order.store_id == store.id, Order.status == "paid", Order.created_at >= start_at, Order.created_at < end_at)
            .group_by(func.date(Order.created_at))
            .order_by(func.date(Order.created_at))
        )
    ).all()
    body = (
        f'<p style="margin:0 0 4px 0;">Sales for <strong>{escape(store.name)}</strong> from '
        f'{start_day.strftime("%d %b")} to {end_day.strftime("%d %b %Y")}.</p>'
        + data_table(
            ["Orders", "Gross sales", "Refunds"],
            [[f"{int(count):,}", escape(format_money(gross, code)), escape(format_money(refund_total, code))]],
            aligns=["center", "center", "center"],
        )
    )
    if daily_rows:
        body += data_table(
            ["Day", "Orders", "Sales"],
            [
                [escape(day.strftime("%a %d %b")), f"{int(row_count):,}", escape(format_money(row_gross, code))]
                for day, row_count, row_gross in daily_rows
            ],
            aligns=["left", "center", "right"],
        )
    return transactional_email(
        heading="Weekly summary",
        preview=f"{int(count):,} orders · {format_money(gross, code)} at {escape(store.name)}",
        body=body,
        badge="Sales",
    )


async def monthly_summary_body(db: AsyncSession, store: Store, year: int, month: int) -> str:
    """One message summarizing a calendar month, with a per-week breakdown."""
    start_day = date(year, month, 1)
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    end_day = next_month - timedelta(days=1)
    start_at = datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc)
    end_at = datetime.combine(next_month, datetime.min.time(), tzinfo=timezone.utc)
    code = store.currency_code
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
    order_rows = (
        await db.execute(
            select(Order.created_at, Order.total).where(
                Order.store_id == store.id, Order.status == "paid", Order.created_at >= start_at, Order.created_at < end_at
            )
        )
    ).all()
    weekly: dict[tuple[int, int], list] = {}
    for created_at, order_total in order_rows:
        week_key = tuple(created_at.isocalendar()[:2])
        bucket = weekly.setdefault(week_key, [0, Decimal("0.00")])
        bucket[0] += 1
        bucket[1] += order_total
    body = (
        f'<p style="margin:0 0 4px 0;">Sales for <strong>{escape(store.name)}</strong> in '
        f'{start_day.strftime("%B %Y")}.</p>'
        + data_table(
            ["Orders", "Gross sales", "Refunds"],
            [[f"{int(count):,}", escape(format_money(gross, code)), escape(format_money(refund_total, code))]],
            aligns=["center", "center", "center"],
        )
    )
    if weekly:
        body += data_table(
            ["Week of", "Orders", "Sales"],
            [
                [escape(date.fromisocalendar(year_, week_, 1).strftime("%d %b")), f"{bucket[0]:,}", escape(format_money(bucket[1], code))]
                for (year_, week_), bucket in sorted(weekly.items())
            ],
            aligns=["left", "center", "right"],
        )
    return transactional_email(
        heading="Monthly summary",
        preview=f"{int(count):,} orders · {format_money(gross, code)} at {escape(store.name)}",
        body=body,
        badge="Sales",
    )


async def operations_digest_body(db: AsyncSession, store: Store, day) -> str | None:
    """One message summarizing the day's in-app-only events, or None if quiet.

    Each event writes one ``Notification`` per manager, so identical entries are
    de-duplicated before the digest is built.
    """
    start_at = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    rows = (
        await db.execute(
            select(Notification.type, Notification.title, Notification.body)
            .where(
                Notification.store_id == store.id,
                Notification.type.in_(DIGEST_TYPES),
                Notification.created_at >= start_at,
                Notification.created_at < end_at,
            )
            .order_by(Notification.created_at)
        )
    ).all()
    if not rows:
        return None
    labels = {
        "approval_request": "Approval",
        "discount_review": "Discount",
        "refund_review": "Refund review",
        "stock_transfer": "Stock transfer",
    }
    seen: set[tuple] = set()
    items: list[list[str]] = []
    for note_type, title, detail in rows:
        key = (note_type, title, detail)
        if key in seen:
            continue
        seen.add(key)
        item = escape(title or "")
        if detail:
            item += f'<br /><span style="color:#92939d;">{escape(detail)}</span>'
        items.append([escape(labels.get(note_type, note_type)), item])
    body = (
        f'<p style="margin:0 0 4px 0;">{len(items)} item(s) need your attention at '
        f"<strong>{escape(store.name)}</strong>.</p>"
        + data_table(["Type", "Item"], items, aligns=["left", "left"])
    )
    return transactional_email(
        heading="Operations summary",
        preview=f"{len(items)} item(s) at {escape(store.name)}.",
        body=body,
        badge="Ops",
        footnote="Turn this summary off in Settings → Notifications.",
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


async def queue_public_order_note(db: AsyncSession, store: Store, held: HeldOrder) -> int:
    """Tell owners a customer just submitted an online or QR order.

    Runs on the public submit path, so callers treat it as best-effort: a mail
    problem must never stop a customer's order from being accepted.
    """
    currency = store.currency_code
    source_label = "QR" if held.source == "qr" else "online"
    lines = held.items or []
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
                escape(format_money(amount, currency)),
            ]
        )
    where = f" for <strong>{escape(held.label)}</strong>" if held.label else ""
    body = (
        f'<p style="margin:0 0 4px 0;">A new {source_label} order arrived at '
        f"<strong>{escape(store.name)}</strong>{where}.</p>"
        + data_table(["Item", "Qty", "Amount"], rows, aligns=["left", "right", "right"])
        + totals_table([("Total", escape(format_money(total, currency)))])
    )
    if held.customer_note:
        body += f'<p style="margin:16px 0 0 0;"><strong>Customer note:</strong> {escape(held.customer_note)}</p>'
    body += '<p style="margin:18px 0 0 0;">Confirm it on the Kitchen or Floor board and settle as usual.</p>'
    return await queue_owner_note(
        db,
        store,
        "online_order",
        f"New {source_label} order · {store.name}",
        transactional_email(
            heading="New online order",
            preview=f"{len(lines)} item(s) · {format_money(total, currency)} at {escape(store.name)}",
            body=body,
            badge="Online order",
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


async def queue_shift_closed_note(db: AsyncSession, store: Store, shift: Shift, cashier: str) -> int:
    """Email owners the closing summary of a shift (a Z-report)."""
    code = store.currency_code
    local = _tz(store.timezone)
    opened = shift.opened_at.astimezone(local).strftime("%Y-%m-%d %H:%M") if shift.opened_at else "earlier"
    closed = shift.closed_at.astimezone(local).strftime("%Y-%m-%d %H:%M") if shift.closed_at else "now"

    def money(value, *, dash: bool = False):
        if value is None:
            return "&mdash;" if dash else escape(format_money(0, code))
        return escape(format_money(value, code))

    rows = [
        ["Cashier", escape(cashier or "&mdash;")],
        ["Opened", escape(opened)],
        ["Closed", escape(closed)],
        ["Orders", f"{shift.orders_count or 0:,}"],
        ["Sales", money(shift.sales_total)],
        ["Cash received", money(shift.cash_received)],
        ["Cash refunds", money(shift.cash_refunds)],
        ["Expected cash", money(shift.expected_cash)],
        ["Counted cash", money(shift.counted_cash, dash=True)],
        ["Difference", money(shift.difference, dash=True)],
    ]
    body = (
        f'<p style="margin:0 0 4px 0;">A shift at <strong>{escape(store.name)}</strong> has been closed.</p>'
        + data_table(["", ""], rows, aligns=["left", "right"], show_header=False)
    )
    if shift.notes:
        body += f'<p style="margin:16px 0 0 0;"><strong>Notes:</strong> {escape(shift.notes)}</p>'
    return await queue_owner_note(
        db,
        store,
        "shift_report",
        f"Shift closed · {store.name}",
        transactional_email(
            heading="Shift closed",
            preview=f"{shift.orders_count or 0} order(s) · {format_money(shift.sales_total or 0, code)} at {escape(store.name)}",
            body=body,
            badge="Shift",
        ),
    )


async def run_store_notifications(db: AsyncSession, *, now: datetime | None = None) -> dict:
    """Queue the time-based owner notes that are due right now.

    Idempotent per local day (daily summary, low stock) and per open shift, so
    running it on a short interval cannot double-send.
    """
    now = now or datetime.now(timezone.utc)
    stats = {"stores": 0, "summaries": 0, "low_stock": 0, "shift_reminders": 0, "sale_digests": 0, "weekly_reports": 0, "monthly_reports": 0, "operations_digests": 0}
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

        if prefs.get("weekly_report") and local.weekday() == WEEKLY_REPORT_WEEKDAY and local.hour >= SUMMARY_HOUR:
            week_key = f"{local.isocalendar()[0]}-W{local.isocalendar()[1]:02d}"
            if state.get("weekly_report") != week_key:
                body = await weekly_summary_body(db, store, local.date())
                stats["weekly_reports"] += await queue_owner_note(db, store, "weekly_report", f"Weekly summary · {store.name}", body)
                state["weekly_report"] = week_key
                changed = True

        if prefs.get("monthly_report") and local.day == 1 and local.hour >= SUMMARY_HOUR:
            previous = local.date().replace(day=1) - timedelta(days=1)
            month_key = f"{previous.year}-{previous.month:02d}"
            if state.get("monthly_report") != month_key:
                body = await monthly_summary_body(db, store, previous.year, previous.month)
                stats["monthly_reports"] += await queue_owner_note(db, store, "monthly_report", f"Monthly summary · {store.name}", body)
                state["monthly_report"] = month_key
                changed = True

        if prefs.get("operations_digest") and local.hour >= SUMMARY_HOUR and state.get("operations_digest") != today:
            digest = await operations_digest_body(db, store, local.date())
            if digest:
                stats["operations_digests"] += await queue_owner_note(db, store, "operations_digest", f"Operations summary · {store.name}", digest)
            state["operations_digest"] = today
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
