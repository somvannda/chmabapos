"""Single source of truth for a company's current plan entitlement.

Billing is prepaid only: a ``Subscription`` with ``status = "active"``
represents paid time between ``starts_at`` and ``ends_at`` (paid by KHQR).
Renewals are manual. A workspace has exactly one **effective plan** at any
moment.

Every gate (features, stores, team, transactions), the workspace API and the
admin dashboard must derive plan entitlements from this module instead of
reading stale ``status = "active"`` rows that ignore ``ends_at``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Plan, Subscription

FREE_PLAN_CODE = "free"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def grace_deadline(subscription: Subscription) -> datetime | None:
    """Moment a paid period truly stops governing: ``ends_at`` + grace."""
    if subscription.ends_at is None:
        return None
    return _as_utc(subscription.ends_at) + timedelta(hours=settings.billing_grace_hours)


def is_in_force(subscription: Subscription | None, *, at: datetime | None = None) -> bool:
    """True when an active prepaid subscription row still governs today.

    Free plans carry no ``ends_at`` and never expire. Paid plans stay fully
    usable for ``settings.billing_grace_hours`` past ``ends_at`` (so a missed
    renewal does not instantly pause stores); only after that do they stop
    governing. A row whose ``starts_at`` is still in the future (e.g. a
    downgrade renewal paid early) does not govern yet.
    """
    if subscription is None or subscription.status != "active":
        return False
    now = at or utc_now()
    if _as_utc(subscription.starts_at) > now:
        return False
    deadline = grace_deadline(subscription)
    if deadline is None:
        return True
    return deadline > now


@dataclass
class Entitlement:
    subscription: Subscription | None
    plan: Plan
    pending: Subscription | None = None
    pending_plan: Plan | None = None
    expired: Subscription | None = None

    def denied_reason(self, *, action: str) -> str:
        if self.expired:
            return f"Your {self.expired.plan_code.title()} plan has expired. Renew your plan to {action}."
        if self.pending:
            name = self.pending_plan.name if self.pending_plan else self.pending.plan_code
            return f"Complete your {name} payment to activate your plan and {action}."
        if self.subscription and self.plan.code == FREE_PLAN_CODE:
            return f"The Free plan does not include this feature. Upgrade your plan to {action}."
        return f"An active plan is required to {action}."


async def load_entitlement(db: AsyncSession, company_id: UUID) -> Entitlement:
    """Resolve the company's governing prepaid plan.

    ``subscription`` is the in-force row (paid or Free); when nothing is in
    force the effective ``plan`` falls back to Free. ``pending``/``expired`` are
    used for messaging so an owner knows to finish a checkout or renew.
    """
    plan_cache: dict[str, Plan | None] = {}

    async def plan_for(code: str) -> Plan | None:
        if code not in plan_cache:
            plan_cache[code] = await db.get(Plan, code)
        return plan_cache[code]

    rows = (
        await db.execute(
            select(Subscription)
            .where(Subscription.company_id == company_id, Subscription.status.in_(["active", "pending"]))
            .order_by(Subscription.created_at.desc())
        )
    ).scalars().all()
    pending = next((row for row in rows if row.status == "pending"), None)
    in_force = next((row for row in rows if is_in_force(row)), None)
    expired = next((row for row in rows if row.status == "active" and row.ends_at is not None and (grace_deadline(row) or _as_utc(row.ends_at)) <= utc_now()), None)
    plan = await plan_for(in_force.plan_code) if in_force else None
    if plan is None:
        plan = await plan_for(FREE_PLAN_CODE)
    if plan is None:
        raise LookupError("Free plan is not configured")
    if in_force and plan.code != in_force.plan_code:
        in_force = None
    pending_plan = await plan_for(pending.plan_code) if pending else None
    return Entitlement(subscription=in_force, plan=plan, pending=pending, pending_plan=pending_plan, expired=expired)
