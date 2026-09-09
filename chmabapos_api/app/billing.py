"""Single source of truth for a company's current plan entitlement.

Two billing models can pay for the same plans, but a workspace has exactly one
**effective plan** at any moment and never pays two providers for the same
period:

* **Prepaid** (default): a ``Subscription`` with ``status = "active"``
  represents paid time between ``starts_at`` and ``ends_at`` (KHQR or one-time
  card via Paddle). Renewals are manual.
* **Recurring** (opt-in): a ``RecurringSubscription`` mirrored from Paddle
  auto-renew webhooks. While in force it governs the workspace and any prepaid
  paid period was forfeited the day it started.

Every gate (features, stores, team, transactions), the workspace API and the
admin dashboard must derive plan entitlements from this module instead of
reading stale ``status = "active"`` rows that ignore ``ends_at``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Plan, RecurringSubscription, Subscription

FREE_PLAN_CODE = "free"

RECURRING_ACTIVE_STATUSES = frozenset({"active", "trialing", "past_due"})


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_in_force(subscription: Subscription | None, *, at: datetime | None = None) -> bool:
    """True when an active prepaid subscription row still governs today.

    Free plans carry no ``ends_at`` and never expire; paid plans expire the
    moment ``ends_at`` passes. A row whose ``starts_at`` is still in the future
    (e.g. a downgrade renewal paid early) does not govern yet.
    """
    if subscription is None or subscription.status != "active":
        return False
    now = at or utc_now()
    if _as_utc(subscription.starts_at) > now:
        return False
    if subscription.ends_at is None:
        return True
    return _as_utc(subscription.ends_at) > now


def recurring_in_force(recurring: RecurringSubscription | None, *, at: datetime | None = None) -> bool:
    """True when a mirrored Paddle auto-renew subscription governs today.

    Governing statuses are ``active``, ``trialing`` and ``past_due`` (dunning
    keeps access). A row is only governing while ``starts_at <= now < ends_at``.
    """
    if recurring is None or recurring.status not in RECURRING_ACTIVE_STATUSES:
        return False
    now = at or utc_now()
    if _as_utc(recurring.starts_at) > now:
        return False
    if recurring.ends_at is None:
        return True
    return _as_utc(recurring.ends_at) > now


@dataclass
class Entitlement:
    subscription: Subscription | None
    plan: Plan
    pending: Subscription | None = None
    pending_plan: Plan | None = None
    expired: Subscription | None = None
    recurring: RecurringSubscription | None = None

    @property
    def is_recurring(self) -> bool:
        """True when a Paddle auto-renew subscription is the governing model."""
        return self.recurring is not None

    def denied_reason(self, *, action: str) -> str:
        if self.expired:
            return f"Your {self.expired.plan_code.title()} plan has expired. Renew your plan to {action}."
        if self.pending:
            name = self.pending_plan.name if self.pending_plan else self.pending.plan_code
            return f"Complete your {name} payment to activate your plan and {action}."
        if self.subscription and self.plan.code == FREE_PLAN_CODE:
            return f"The Free plan does not include this feature. Upgrade your plan to {action}."
        if self.recurring and self.recurring.status == "past_due":
            return f"Your {self.plan.code.title()} payment is past due. Update your payment method in Paddle to {action}."
        return f"An active plan is required to {action}."


async def load_entitlement(db: AsyncSession, company_id: UUID) -> Entitlement:
    """Resolve the company's governing plan across both billing models.

    A governing ``RecurringSubscription`` (Paddle auto-renew) takes precedence
    over prepaid rows. ``subscription`` stays the in-force *prepaid* row (paid
    or Free) for prepaid-only workspaces; ``recurring`` is set when Paddle
    auto-renew governs. When nothing is in force the effective ``plan`` falls
    back to Free. ``pending``/``expired`` are prepaid-only, used for messaging
    so an owner knows to finish a checkout.
    """
    plan_cache: dict[str, Plan | None] = {}

    async def plan_for(code: str) -> Plan | None:
        if code not in plan_cache:
            plan_cache[code] = await db.get(Plan, code)
        return plan_cache[code]

    recurring_rows = (
        await db.execute(
            select(RecurringSubscription)
            .where(RecurringSubscription.company_id == company_id, RecurringSubscription.status.in_(RECURRING_ACTIVE_STATUSES))
            .order_by(RecurringSubscription.created_at.desc())
        )
    ).scalars().all()
    governing_recurring = next((row for row in recurring_rows if recurring_in_force(row)), None)
    if governing_recurring is not None:
        plan = await plan_for(governing_recurring.plan_code)
        if plan is None:
            plan = await plan_for(FREE_PLAN_CODE)
        if plan is None:
            raise LookupError("Free plan is not configured")
        return Entitlement(subscription=None, plan=plan, recurring=governing_recurring)

    rows = (
        await db.execute(
            select(Subscription)
            .where(Subscription.company_id == company_id, Subscription.status.in_(["active", "pending"]))
            .order_by(Subscription.created_at.desc())
        )
    ).scalars().all()
    pending = next((row for row in rows if row.status == "pending"), None)
    in_force = next((row for row in rows if is_in_force(row)), None)
    expired = next((row for row in rows if row.status == "active" and row.ends_at is not None and _as_utc(row.ends_at) <= utc_now()), None)
    plan = await plan_for(in_force.plan_code) if in_force else None
    if plan is None:
        plan = await plan_for(FREE_PLAN_CODE)
    if plan is None:
        raise LookupError("Free plan is not configured")
    if in_force and plan.code != in_force.plan_code:
        in_force = None
    pending_plan = await plan_for(pending.plan_code) if pending else None
    return Entitlement(subscription=in_force, plan=plan, pending=pending, pending_plan=pending_plan, expired=expired)
