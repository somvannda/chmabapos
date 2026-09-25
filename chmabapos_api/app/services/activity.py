"""Cross-tenant activity recording and real-time Telegram forwarding.

Every meaningful platform event is written to ``platform_activities`` and, when
Telegram is configured, forwarded to the internal operations group. The same
rows back the daily digest aggregates.

``record_activity`` is called as the final step of a request, immediately before
its ``commit``. The Telegram send is attempted inline and is best-effort: a slow
or unreachable Telegram API must never fail a signup, login, sale or payment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import PlatformActivity, User
from app.telegram import send_telegram_message

EVENT_TITLES: dict[str, str] = {
    "user.registered": "New signup",
    "user.google_signup": "New signup (Google)",
    "user.email_verified": "Email verified",
    "user.logged_in": "Login",
    "user.google_login": "Login (Google)",
    "user.password_reset_requested": "Password reset requested",
    "user.password_reset": "Password reset",
    "billing.plan_paid": "Plan payment received",
    "order.paid": "Sale completed",
    "order.refunded": "Refund issued",
    "inventory.transferred": "Stock transfer",
    "team.invited": "Team invitation sent",
    "team.invitation_accepted": "Team invitation accepted",
}

# Preferred display order for the free-form ``details`` payload.
_DETAIL_ORDER = ("company", "store", "from_store", "to_store", "plan", "cycle", "order_number", "method", "role", "items", "reference", "full_name", "amount")
_DETAIL_LABELS = {
    "company": "Company",
    "store": "Store",
    "from_store": "From",
    "to_store": "To",
    "plan": "Plan",
    "cycle": "Cycle",
    "order_number": "Order",
    "method": "Method",
    "role": "Role",
    "items": "Items",
    "reference": "Reference",
    "full_name": "Name",
    "amount": "Amount",
}


def local_now() -> datetime:
    """Current time in the configured digest timezone (UTC+7 fallback)."""
    from app.services.telegram_digest import digest_timezone

    return datetime.now(timezone.utc).astimezone(digest_timezone())


def render_activity(event_type: str, *, email: str | None = None, details: dict[str, Any] | None = None) -> str:
    title = EVENT_TITLES.get(event_type, event_type)
    details = details or {}
    lines = [title]
    if email:
        lines.append(f"Email: {email}")
    seen: set[str] = set()
    for key in (*_DETAIL_ORDER, *details.keys()):
        if key in seen or key not in details or details[key] in (None, ""):
            continue
        seen.add(key)
        lines.append(f"{_DETAIL_LABELS.get(key, key.title().replace('_', ' '))}: {details[key]}")
    lines.append(f"Time: {local_now():%Y-%m-%d %H:%M}")
    return "\n".join(lines)


def event_message(event_type: str, *, email: str | None = None, details: dict[str, Any] | None = None) -> str:
    return render_activity(event_type, email=email, details=details)


async def record_activity(
    db: AsyncSession,
    event_type: str,
    *,
    user: User | None = None,
    email: str | None = None,
    company_id: UUID | None = None,
    store_id: UUID | None = None,
    details: dict[str, Any] | None = None,
    notify: bool = True,
) -> PlatformActivity:
    """Persist a platform event and best-effort forward it to Telegram."""
    resolved_email = email or (user.email if user else None)
    activity = PlatformActivity(
        user_id=user.id if user else None,
        company_id=company_id,
        store_id=store_id,
        event_type=event_type,
        email=resolved_email,
        details=details,
    )
    db.add(activity)
    if notify and settings.telegram_enabled:
        await send_telegram_message(render_activity(event_type, email=resolved_email, details=details))
    return activity
