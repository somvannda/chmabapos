"""Daily billing lifecycle: expire paid plans, fall back to Free, restore.

When a paid prepaid period ends (``ends_at`` passes) with no renewal payment the
workspace keeps its data but drops to the Free plan:

* the overdue paid subscription is marked ``expired``;
* a Free fallback subscription is provisioned (if none is already in force);
* stores beyond Free capacity are **paused** and staff (non-owner) memberships
  are **revoked**, keeping all owners so nobody is locked out;
* the exact items force-paused are recorded on the fallback subscription so a
  later payment can restore precisely those up to the new plan's capacity.

Selection is by activity: the most recently used store stays selling on Free,
and on restore the most recently active paused items come back first.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import FREE_PLAN_CODE
from app.models import Membership, Order, Plan, Store, Subscription

OWNER_ROLE = "owner"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _store_activity(db: AsyncSession, company_id: UUID) -> dict[UUID, datetime]:
    rows = (
        await db.execute(
            select(Order.store_id, func.max(Order.created_at))
            .join(Store, Store.id == Order.store_id)
            .where(Store.company_id == company_id, Order.status == "paid")
            .group_by(Order.store_id)
        )
    ).all()
    return {store_id: last for store_id, last in rows}


async def _member_activity(db: AsyncSession, company_id: UUID) -> dict[UUID, datetime]:
    rows = (
        await db.execute(
            select(Order.created_by, func.max(Order.created_at))
            .join(Store, Store.id == Order.store_id)
            .where(Store.company_id == company_id, Order.status == "paid")
            .group_by(Order.created_by)
        )
    ).all()
    return {user_id: last for user_id, last in rows}


def _rank_created(created_at: datetime) -> float:
    return -created_at.timestamp()


async def pause_stores_over_capacity(db: AsyncSession, company_id: UUID, *, limit: int) -> list[str]:
    """Deactivate active stores beyond ``limit``; keep the most recently used.

    Returns the paused store ids ordered most-recently-active first (for
    partial restore later).
    """
    if limit < 1:
        return []
    stores = (await db.execute(select(Store).where(Store.company_id == company_id, Store.is_active.is_(True)))).scalars().all()
    if len(stores) <= limit:
        return []
    activity = await _store_activity(db, company_id)
    ranked = sorted(
        stores,
        key=lambda s: (activity.get(s.id).timestamp() if s.id in activity else 0.0, _rank_created(s.created_at)),
        reverse=True,
    )
    paused = ranked[limit:]
    paused_ids: list[str] = []
    for store in paused:
        store.is_active = False
        paused_ids.append(str(store.id))
    return paused_ids


async def revoke_staff_over_capacity(db: AsyncSession, company_id: UUID) -> list[str]:
    """Revoke active non-owner memberships; owners are always kept.

    Returns the revoked membership ids ordered most-recently-active first.
    """
    members = (
        await db.execute(
            select(Membership).where(
                Membership.company_id == company_id,
                Membership.role != OWNER_ROLE,
                Membership.status == "active",
            )
        )
    ).scalars().all()
    if not members:
        return []
    activity = await _member_activity(db, company_id)
    ranked = sorted(
        members,
        key=lambda m: (activity.get(m.user_id).timestamp() if m.user_id in activity else 0.0, _rank_created(m.created_at)),
        reverse=True,
    )
    revoked_ids: list[str] = []
    for member in ranked:
        member.status = "revoked"
        revoked_ids.append(str(member.id))
    return revoked_ids


async def _free_plan(db: AsyncSession) -> Plan:
    plan = await db.get(Plan, FREE_PLAN_CODE)
    if plan is None:
        raise LookupError("Free plan is not configured")
    return plan


async def expire_company_subscriptions(db: AsyncSession, company_id: UUID) -> dict:
    """Expire overdue paid plans for one company and provision the Free fallback."""
    now = utc_now()
    overdue = (
        await db.execute(
            select(Subscription).where(
                Subscription.company_id == company_id,
                Subscription.status == "active",
                Subscription.plan_code != FREE_PLAN_CODE,
                Subscription.ends_at.is_not(None),
                Subscription.ends_at <= now,
            )
        )
    ).scalars().all()
    if not overdue:
        return {"expired_subs": 0, "paused_stores": [], "revoked_members": []}

    existing_free = (
        await db.execute(
            select(Subscription).where(
                Subscription.company_id == company_id,
                Subscription.status == "active",
                Subscription.plan_code == FREE_PLAN_CODE,
            )
        )
    ).scalars().first()
    paused_stores: list[str] = []
    revoked_members: list[str] = []
    if existing_free is None:
        free_plan = await _free_plan(db)
        paused_stores = await pause_stores_over_capacity(db, company_id, limit=free_plan.max_stores)
        revoked_members = await revoke_staff_over_capacity(db, company_id)
        fallback = Subscription(
            company_id=company_id,
            plan_code=FREE_PLAN_CODE,
            billing_cycle="monthly",
            status="active",
            starts_at=now,
            ends_at=None,
            paused_store_ids=paused_stores,
            paused_member_ids=revoked_members,
        )
        db.add(fallback)
    for subscription in overdue:
        subscription.status = "expired"
        subscription.scheduled_plan_code = None
        subscription.scheduled_store_ids = None
        subscription.scheduled_member_ids = None
    return {"expired_subs": len(overdue), "paused_stores": paused_stores, "revoked_members": revoked_members}


async def run_expiry_job(db: AsyncSession) -> dict:
    """Find every company with an overdue paid plan and apply the Free fallback.

    Safe to run repeatedly: once a subscription is marked ``expired`` it is no
    longer selected, and the fallback is only created when none is in force.
    """
    overdue = (
        await db.execute(
            select(Subscription).where(
                Subscription.status == "active",
                Subscription.plan_code != FREE_PLAN_CODE,
                Subscription.ends_at.is_not(None),
                Subscription.ends_at <= utc_now(),
            )
        )
    ).scalars().all()
    company_ids = list(dict.fromkeys(str(row.company_id) for row in overdue))
    stats = {"companies": 0, "expired_subs": 0, "paused_stores": 0, "revoked_members": 0}
    for company_id in company_ids:
        result = await expire_company_subscriptions(db, UUID(company_id))
        stats["companies"] += 1
        stats["expired_subs"] += result["expired_subs"]
        stats["paused_stores"] += len(result["paused_stores"])
        stats["revoked_members"] += len(result["revoked_members"])
    return stats


async def restore_capacity(
    db: AsyncSession,
    company_id: UUID,
    *,
    plan: Plan,
    store_ids: Sequence[str] = (),
    member_ids: Sequence[str] = (),
) -> dict:
    """Re-activate force-paused stores/members up to the in-force plan's limits.

    ``store_ids``/``member_ids`` come from a fallback subscription's paused
    snapshot and are already ordered most-recently-active first, so when the
    new plan cannot fit everyone the most active items return first.
    """
    restored = {"stores": 0, "members": 0}
    active_stores = await db.scalar(select(func.count(Store.id)).where(Store.company_id == company_id, Store.is_active.is_(True)))
    room = plan.max_stores - (active_stores or 0)
    for raw_id in store_ids:
        if room <= 0:
            break
        store = await db.get(Store, UUID(raw_id))
        if store is not None and store.company_id == company_id and not store.is_active:
            store.is_active = True
            restored["stores"] += 1
            room -= 1

    active_members = await db.scalar(
        select(func.count(Membership.id)).where(Membership.company_id == company_id, Membership.status == "active")
    )
    room = plan.max_members - (active_members or 0)
    for raw_id in member_ids:
        if room <= 0:
            break
        member = await db.get(Membership, UUID(raw_id))
        if member is not None and member.company_id == company_id and member.status == "revoked" and member.role != OWNER_ROLE:
            member.status = "active"
            restored["members"] += 1
            room -= 1
    return restored
