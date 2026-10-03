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
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailSend, InventoryBalance, Membership, Order, Product, Refund, Shift, Store, User
from app.services.sale_emails import format_money, notification_prefs

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
    return "\n".join(
        [
            f"Daily summary for {store.name} on {day.isoformat()}",
            "",
            f"Orders: {int(count)}",
            f"Gross sales: {format_money(gross, store.currency_code)}",
            f"Refunds: {format_money(refund_total, store.currency_code)}",
            "",
            "Sent by Chmaba",
        ]
    )


async def low_stock_body(db: AsyncSession, store: Store) -> tuple[str, str] | None:
    rows = (
        await db.execute(
            select(Product.name, InventoryBalance.on_hand, InventoryBalance.reorder_point)
            .join(Product, Product.id == InventoryBalance.product_id)
            .where(InventoryBalance.store_id == store.id, InventoryBalance.on_hand <= InventoryBalance.reorder_point)
            .order_by(InventoryBalance.on_hand)
        )
    ).all()
    if not rows:
        return None
    lines = [f"Low stock at {store.name}:", ""] + [f"- {name}: {on_hand} left (reorder at {reorder})" for name, on_hand, reorder in rows]
    lines += ["", "Sent by Chmaba"]
    return f"Low stock alert · {store.name}", "\n".join(lines)


async def queue_refund_note(db: AsyncSession, store: Store, *, order_number: str, total, currency_code: str, method: str, actor: str) -> int:
    subject = f"Refund · {store.name} · {format_money(total, currency_code)}"
    body = "\n".join(
        [
            f"A refund was recorded at {store.name}.",
            "",
            f"Order: {order_number}",
            f"Amount: {format_money(total, currency_code)}",
            f"Method: {method.title()}",
            f"By: {actor}",
            "",
            "Sent by Chmaba",
        ]
    )
    return await queue_owner_note(db, store, "refund_activity", subject, body)


async def queue_team_activity(db: AsyncSession, company_id: UUID, *, title: str, detail: str) -> int:
    """Team changes are company-wide, so send if any active store opted in."""
    stores = (
        await db.execute(select(Store).where(Store.company_id == company_id, Store.is_active.is_(True)).order_by(Store.created_at))
    ).scalars().all()
    store = next((candidate for candidate in stores if is_enabled(candidate, "team_activity")), None)
    if store is None:
        return 0
    body = "\n".join([detail, "", "Sent by Chmaba"])
    return await queue_owner_note(db, store, "team_activity", title, body)


async def run_store_notifications(db: AsyncSession, *, now: datetime | None = None) -> dict:
    """Queue the time-based owner notes that are due right now.

    Idempotent per local day (daily summary, low stock) and per open shift, so
    running it on a short interval cannot double-send.
    """
    now = now or datetime.now(timezone.utc)
    stats = {"stores": 0, "summaries": 0, "low_stock": 0, "shift_reminders": 0}
    stores = (await db.execute(select(Store).where(Store.is_active.is_(True)))).scalars().all()
    for store in stores:
        prefs = notification_prefs(store)
        if not any(prefs.get(key) for key in TIME_BASED_KEYS):
            continue
        stats["stores"] += 1
        local = now.astimezone(_tz(store.timezone))
        today = local.date().isoformat()
        state = _state(store)
        changed = False

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
                body = "\n".join(
                    [
                        f"A shift at {store.name} has been open for more than {SHIFT_REMINDER_HOURS} hours.",
                        "",
                        f"Opened: {opened}",
                        "",
                        "Sent by Chmaba",
                    ]
                )
                stats["shift_reminders"] += await queue_owner_note(db, store, "shift_reminders", f"Shift still open · {store.name}", body)
                reminded[shift_id] = now.isoformat()
            state["shifts"] = reminded
            changed = True

        if changed:
            _save_state(store, state)

    await db.commit()
    return stats
