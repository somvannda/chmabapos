"""Paddle auto-renew subscription sync for Chmaba workspaces.

Keeps the Paddle recurring model in a dedicated table
(``RecurringSubscription``) so the prepaid ``Subscription`` lifecycle (KHQR /
one-time card) is untouched. Webhooks are the source of truth: Paddle is where
billing happens (renewals, prorations, cancel/pause scheduling), this module
just mirrors state and enforces Chmaba capacity.

Invariants
----------
* A workspace never pays two providers for the same period. Activating a
  recurring plan forfeits any in-force prepaid paid period that day (the same
  no-credit policy as a prepaid upgrade).
* ``recurring_in_force`` (app.billing) is the only judge of whether the row
  governs today. Terminal / paused rows fall the workspace back to Free using
  the same force-pause + Free-fallback logic as prepaid expiry.
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import FREE_PLAN_CODE, is_in_force
from app.models import Company, Membership, Plan, RecurringSubscription, Subscription, User
from app.services.billing_lifecycle import enforce_plan_capacity, pause_stores_over_capacity, restore_capacity, revoke_staff_over_capacity
from app.services.platform_config import load_paddle_settings

OWNER_ROLE = "owner"

_CYCLE_DAYS = {"monthly": 30, "semi_annual": 182, "annual": 365}
ACTIVE_STATUSES = frozenset({"active", "trialing", "past_due"})
TERMINAL_STATUSES = frozenset({"canceled", "expired", "paused"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def cycle_days(billing_cycle: str) -> int:
    return _CYCLE_DAYS.get(billing_cycle, 30)


async def _company_for_customer(db: AsyncSession, customer_id: str, email: str | None = None) -> Company | None:
    """Find a workspace by Paddle customer id, bridging via owner email when new.

    Once matched the ``companies.paddle_customer_id`` is stored so later
    webhooks resolve in one query.
    """
    if customer_id:
        company = await db.scalar(select(Company).where(Company.paddle_customer_id == customer_id))
        if company is not None:
            return company
    if email:
        row = (
            await db.execute(
                select(Company)
                .join(Membership, Membership.company_id == Company.id)
                .join(User, User.id == Membership.user_id)
                .where(User.email == email.lower(), Membership.role == OWNER_ROLE, Membership.status == "active")
                .limit(1)
            )
        ).scalars().first()
        if row is not None:
            if customer_id:
                row.paddle_customer_id = customer_id
            await db.flush()
            return row
    return None


def _resolve_plan_cycle(
    price_ids: dict[str, str],
    *,
    price_id: str | None = None,
    plan_code: str | None = None,
    billing_cycle: str | None = None,
) -> tuple[str | None, str | None]:
    if price_id:
        for key, value in price_ids.items():
            if value == price_id and ":" in key:
                if key.startswith("recurring:"):
                    key = key[len("recurring:"):]
                code, cycle = key.split(":", 1)
                return code, cycle
    return plan_code, billing_cycle


async def _free_plan(db: AsyncSession) -> Plan:
    plan = await db.get(Plan, FREE_PLAN_CODE)
    if plan is None:
        raise LookupError("Free plan is not configured")
    return plan


async def _ensure_free_fallback(db: AsyncSession, company_id: UUID) -> Subscription:
    """Guarantee an in-force prepaid Free row, pausing/revoking beyond Free.

    Returns the Free row. Safe to call repeatedly: it no-ops when an in-force
    Free subscription already governs the workspace.
    """
    actives = (await db.execute(select(Subscription).where(Subscription.company_id == company_id, Subscription.status == "active"))).scalars().all()
    free_row = next((row for row in actives if row.plan_code == FREE_PLAN_CODE), None)
    if free_row is not None and is_in_force(free_row):
        return free_row
    free_plan = await _free_plan(db)
    paused_stores = await pause_stores_over_capacity(db, company_id, limit=free_plan.max_stores)
    revoked_members = await revoke_staff_over_capacity(db, company_id)
    now = _utc_now()
    row = Subscription(
        company_id=company_id,
        plan_code=FREE_PLAN_CODE,
        billing_cycle="monthly",
        status="active",
        starts_at=now,
        ends_at=None,
        paused_store_ids=paused_stores,
        paused_member_ids=revoked_members,
    )
    db.add(row)
    await db.flush()
    return row


async def _takeover_prepaid(db: AsyncSession, company: Company, plan_code: str) -> None:
    """Forfeit in-force prepaid paid periods the day a recurring plan starts.

    Matches the existing upgrade policy: the old paid period ends that day with
    no credit or refund. Free fallback rows are left in place (they only govern
    again if the recurring plan later ends).
    """
    paid = (
        await db.execute(
            select(Subscription).where(
                Subscription.company_id == company.id,
                Subscription.status == "active",
                Subscription.plan_code != FREE_PLAN_CODE,
            )
        )
    ).scalars().all()
    now = _utc_now()
    for row in paid:
        if is_in_force(row):
            row.status = "canceled"
            row.ends_at = now
            row.scheduled_plan_code = None
            row.scheduled_store_ids = None
            row.scheduled_member_ids = None
    pending = (
        await db.execute(select(Subscription).where(Subscription.company_id == company.id, Subscription.status == "pending"))
    ).scalars().all()
    for row in pending:
        row.status = "canceled"
        row.ends_at = now


async def _provision_plan(db: AsyncSession, company_id: UUID, recurring_row: RecurringSubscription, plan: Plan) -> None:
    """Restore any force-paused items from a Free fallback, then enforce capacity.

    Mirrors what prepaid ``fulfill_billing_payment`` does so a workspace that
    was on Free after prepaid expiry regains its stores/team up to the new
    plan's limits, most-recently-active first.
    """
    free_rows = (await db.execute(select(Subscription).where(Subscription.company_id == company_id, Subscription.status == "active", Subscription.plan_code == FREE_PLAN_CODE))).scalars().all()
    store_ids: list[str] = []
    member_ids: list[str] = []
    for row in free_rows:
        if row.paused_store_ids and not store_ids:
            store_ids = list(row.paused_store_ids or [])
        if row.paused_member_ids and not member_ids:
            member_ids = list(row.paused_member_ids or [])
    if store_ids or member_ids:
        await restore_capacity(db, company_id, plan=plan, store_ids=store_ids, member_ids=member_ids)
    await enforce_plan_capacity(db, company_id, subscription=recurring_row, plan=plan)


async def _retire_to_free(db: AsyncSession, company_id: UUID) -> None:
    """Drop the workspace back to Free after a recurring plan ends or pauses."""
    await _ensure_free_fallback(db, company_id)
    # No other paid source can be in force (takeover forfeited prepaid), so no
    # extra cleanup is required; the resolver now returns Free for this company.


async def sync_subscription_state(
    db: AsyncSession,
    *,
    paddle_subscription_id: str,
    customer_id: str | None,
    customer_email: str | None,
    price_id: str | None,
    plan_code: str | None,
    billing_cycle: str | None,
    status: str,
    starts_at: datetime | None,
    ends_at: datetime | None,
    scheduled_action: str | None = None,
    scheduled_effective_at: datetime | None = None,
    company_override: UUID | None = None,
    customer_email_resolver: Callable[[str], Awaitable[str | None]] | None = None,
) -> bool:
    """Idempotent sync of one Paddle subscription. Returns True when applied.

    For a brand-new subscription the owning workspace is resolved from the
    Paddle customer (by stored ``paddle_customer_id``, else the customer email
    matching an active owner). When neither matches, ``customer_email_resolver``
    may look the email up from Paddle (``GET /customers/{id}``) and retry.
    Tests/dev helpers can pass ``company_override`` to skip the lookup.
    """
    price_ids: dict[str, str] = {}
    try:
        cfg = await load_paddle_settings(db)
        price_ids = cfg.get("paddle_price_ids") or {}
    except Exception:  # settings load must never block webhook processing
        pass

    resolved_plan, resolved_cycle = _resolve_plan_cycle(price_ids, price_id=price_id, plan_code=plan_code, billing_cycle=billing_cycle)

    existing = await db.scalar(select(RecurringSubscription).where(RecurringSubscription.paddle_subscription_id == paddle_subscription_id))
    terminal = status in TERMINAL_STATUSES

    if existing is None:
        if terminal or not resolved_plan:
            return False
        if company_override is not None:
            company = await db.get(Company, company_override)
        else:
            company = await _company_for_customer(db, customer_id or "", customer_email)
            if company is None and customer_id and customer_email_resolver is not None:
                try:
                    fetched = await customer_email_resolver(customer_id)
                except Exception:
                    fetched = None
                if fetched:
                    company = await _company_for_customer(db, customer_id or "", fetched)
        if company is None:
            return False
        now = _utc_now()
        row = RecurringSubscription(
            company_id=company.id,
            paddle_subscription_id=paddle_subscription_id,
            paddle_customer_id=customer_id,
            price_id=price_id,
            plan_code=resolved_plan,
            billing_cycle=resolved_cycle or "monthly",
            status=status,
            starts_at=_as_utc(starts_at) if starts_at else now,
            ends_at=_as_utc(ends_at) if ends_at else None,
        )
        db.add(row)
        company_id = company.id
        is_new = True
        reactivation = False
        plan_changed = False
    else:
        company = await db.get(Company, existing.company_id)
        if company is None:
            return False
        company_id = existing.company_id
        row = existing
        row.paddle_customer_id = customer_id or existing.paddle_customer_id
        row.price_id = price_id or existing.price_id
        is_new = False
        reactivation = existing.status in TERMINAL_STATUSES and status in ACTIVE_STATUSES
        plan_changed = (resolved_plan or existing.plan_code) != existing.plan_code or (resolved_cycle or existing.billing_cycle) != existing.billing_cycle
        if resolved_plan:
            row.plan_code = resolved_plan
            row.billing_cycle = resolved_cycle or existing.billing_cycle

    now = _utc_now()
    if terminal:
        # canceled / expired / paused no longer govern (the resolver only
        # considers ACTIVE_STATUSES). Paddle only sends subscription.canceled
        # once the subscription has actually ended, so fall the workspace back
        # to Free immediately (paused drops at once too — billing and service
        # are paused in Paddle). Pending cancels arrive first as an active
        # status with a scheduled_change and stay governing until the period
        # ends.
        row.status = status
        row.ends_at = _as_utc(ends_at) if ends_at else row.ends_at
        row.scheduled_action = None
        row.scheduled_effective_at = None
        row.updated_at = now
        await _retire_to_free(db, company_id)
    else:
        row.status = status
        row.starts_at = _as_utc(starts_at) if starts_at else row.starts_at
        row.ends_at = _as_utc(ends_at) if ends_at else row.ends_at
        row.scheduled_action = scheduled_action
        row.scheduled_effective_at = scheduled_effective_at
        row.updated_at = now
        if is_new or reactivation or plan_changed:
            if company is not None:
                await _takeover_prepaid(db, company, row.plan_code)
            plan = await db.get(Plan, row.plan_code)
            if plan is not None:
                await _provision_plan(db, company_id, row, plan)
    await db.commit()
    return True


async def apply_paddle_event(
    db: AsyncSession,
    event_type: str,
    data: dict,
    occurred_at: datetime | None = None,
    customer_email_resolver: Callable[[str], Awaitable[str | None]] | None = None,
) -> bool:
    """Route a Paddle ``subscription.*`` event payload to sync."""
    if not event_type.startswith("subscription."):
        return False
    if event_type not in {"subscription.created", "subscription.updated", "subscription.activated", "subscription.canceled", "subscription.past_due", "subscription.paused", "subscription.resumed"}:
        return False
    period = data.get("current_billing_period") or {}
    items = data.get("items") or []
    price = (items[0] or {}).get("price") if items else None
    scheduled = data.get("scheduled_change") or {}
    return await sync_subscription_state(
        db,
        paddle_subscription_id=data.get("id", ""),
        customer_id=data.get("customer_id"),
        customer_email=(data.get("customer") or {}).get("email"),
        price_id=(price or {}).get("id"),
        plan_code=None,
        billing_cycle=None,
        status=data.get("status", "active"),
        starts_at=_parse_dt(period.get("starts_at")),
        ends_at=_parse_dt(period.get("ends_at")),
        scheduled_action=scheduled.get("action"),
        scheduled_effective_at=_parse_dt(scheduled.get("effective_at")),
        customer_email_resolver=customer_email_resolver,
    )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def mock_activate(db: AsyncSession, company_id: UUID, plan_code: str, billing_cycle: str) -> RecurringSubscription:
    """Dev/test helper: activate a fake Paddle subscription for a workspace."""
    company = await db.get(Company, company_id)
    if company is None:
        raise LookupError("Company not found")
    subscription_id = f"mock_sub_{uuid.uuid4().hex}"
    now = _utc_now()
    ok = await sync_subscription_state(
        db,
        paddle_subscription_id=subscription_id,
        customer_id=f"mock_ctm_{uuid.uuid4().hex}",
        customer_email=None,
        price_id=f"pri_mock_{plan_code}_{billing_cycle}",
        plan_code=plan_code,
        billing_cycle=billing_cycle,
            status="active",
            starts_at=now,
            ends_at=now + timedelta(days=cycle_days(billing_cycle)),
            company_override=company_id,
        )
    if not ok:
        raise LookupError("Could not activate mock recurring subscription")
    row = await db.scalar(select(RecurringSubscription).where(RecurringSubscription.paddle_subscription_id == subscription_id))
    if row is None:
        raise LookupError("Mock recurring subscription missing after activation")
    return row
