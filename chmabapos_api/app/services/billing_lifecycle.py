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
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import FREE_PLAN_CODE, is_in_force
from app.config import settings
from app.models import Membership, Order, Plan, Store, Subscription, SubscriptionCapacityAction

OWNER_ROLE = "owner"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def record_capacity_actions(
    db: AsyncSession,
    *,
    subscription: Subscription,
    resource_type: str,
    resource_ids: Sequence[str],
    action: str,
    reason: str,
) -> None:
    """Append an audit row for each forced store/member pause or restore.

    ``subscription`` is the subscription whose limits forced the action (the
    Free fallback, a downgraded plan, or the plan that restored capacity).
    """
    now = utc_now()
    for raw_id in resource_ids:
        db.add(
            SubscriptionCapacityAction(
                subscription_id=subscription.id,
                company_id=subscription.company_id,
                resource_type=resource_type,
                resource_id=UUID(raw_id),
                action=action,
                reason=reason,
                created_at=now,
            )
        )


async def _mark_capacity_restored(
    db: AsyncSession, *, company_id: UUID, resource_type: str, resource_ids: Sequence[str]
) -> None:
    """Stamp ``restored_at`` on the still-open pause rows for these resources."""
    if not resource_ids:
        return
    parsed = [UUID(raw_id) for raw_id in resource_ids]
    rows = (
        await db.execute(
            select(SubscriptionCapacityAction).where(
                SubscriptionCapacityAction.company_id == company_id,
                SubscriptionCapacityAction.resource_type == resource_type,
                SubscriptionCapacityAction.action == "pause",
                SubscriptionCapacityAction.resource_id.in_(parsed),
                SubscriptionCapacityAction.restored_at.is_(None),
            )
        )
    ).scalars().all()
    now = utc_now()
    for row in rows:
        row.restored_at = now


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


async def pause_stores_over_capacity(
    db: AsyncSession, company_id: UUID, *, limit: int, preferred_store_id: str | None = None
) -> list[str]:
    """Deactivate active stores beyond ``limit``; keep the most recently used.

    When ``preferred_store_id`` names an active store it is always kept first
    (used to honour an owner's chosen store when a workspace falls to Free).
    Returns the paused store ids ordered most-recently-active first.
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
    if preferred_store_id:
        preferred = next((store for store in ranked if str(store.id) == preferred_store_id), None)
        if preferred is not None:
            ranked = [preferred] + [store for store in ranked if store is not preferred]
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


async def enforce_plan_capacity(
    db: AsyncSession,
    company_id: UUID,
    *,
    subscription: Subscription,
    plan: Plan,
    keep_store_ids: Sequence[str] = (),
    keep_member_ids: Sequence[str] = (),
    reason: str = "downgrade",
) -> dict:
    """Make the active store/member set fit ``plan``.

    Used when a smaller paid plan takes over (scheduled downgrade): stores and
    non-owner members beyond the plan's limits are paused/revoked. With keep
    lists the owner's exact choices are honoured (owners are always kept);
    without them the most recently active items are kept. Everything force-paused
    here is recorded on ``subscription`` so a later upgrade can restore it.
    """
    stores = (await db.execute(select(Store).where(Store.company_id == company_id))).scalars().all()
    active_stores = [store for store in stores if store.is_active]
    activity = await _store_activity(db, company_id)
    ranked = sorted(
        active_stores,
        key=lambda s: (activity.get(s.id).timestamp() if s.id in activity else 0.0, _rank_created(s.created_at)),
        reverse=True,
    )
    keep_ids = {raw for raw in keep_store_ids}
    if keep_store_ids:
        desired = [store for store in stores if str(store.id) in keep_ids][: plan.max_stores]
    else:
        desired = ranked[: plan.max_stores]
    desired_ids = {str(store.id) for store in desired}
    paused_store_ids = [str(store.id) for store in ranked if str(store.id) not in desired_ids]
    for store in stores:
        store.is_active = str(store.id) in desired_ids

    members = (await db.execute(select(Membership).where(Membership.company_id == company_id))).scalars().all()
    owners = [member for member in members if member.role == OWNER_ROLE]
    owners_ids = {str(member.id) for member in owners}
    active_staff = [member for member in members if member.role != OWNER_ROLE and member.status == "active"]
    staff_activity = await _member_activity(db, company_id)
    ranked_staff = sorted(
        active_staff,
        key=lambda m: (staff_activity.get(m.user_id).timestamp() if m.user_id in staff_activity else 0.0, _rank_created(m.created_at)),
        reverse=True,
    )
    keep_member_set = {raw for raw in keep_member_ids}
    room = max(plan.max_members - len(owners), 0)
    if keep_member_ids:
        selected_staff = [member for member in members if member.role != OWNER_ROLE and str(member.id) in keep_member_set][:room]
    else:
        selected_staff = ranked_staff[:room]
    desired_member_ids = owners_ids | {str(member.id) for member in selected_staff}
    paused_member_ids = [str(member.id) for member in ranked_staff if str(member.id) not in desired_member_ids]
    for member in members:
        if member.role == OWNER_ROLE:
            if member.status != "active":
                member.status = "active"
        elif str(member.id) in desired_member_ids:
            if member.status != "active":
                member.status = "active"
        elif member.status == "active":
            member.status = "revoked"
    subscription.paused_store_ids = paused_store_ids
    subscription.paused_member_ids = paused_member_ids
    if paused_store_ids:
        await record_capacity_actions(
            db, subscription=subscription, resource_type="store", resource_ids=paused_store_ids, action="pause", reason=reason
        )
    if paused_member_ids:
        await record_capacity_actions(
            db, subscription=subscription, resource_type="member", resource_ids=paused_member_ids, action="pause", reason=reason
        )
    return {"stores": paused_store_ids, "members": paused_member_ids}


async def expire_company_subscriptions(db: AsyncSession, company_id: UUID) -> dict:
    """Expire overdue paid plans for one company at their period boundary.

    If a paid renewal already took over (a scheduled downgrade that was paid and
    started at the old ``ends_at``), the overdue rows are just marked ``expired``
    and the successor's capacity is enforced against its keep-lists — the company
    never drops to Free. Otherwise the Free fallback is provisioned.
    """
    now = utc_now()
    cutoff = now - timedelta(hours=settings.billing_grace_hours)
    overdue = (
        await db.execute(
            select(Subscription).where(
                Subscription.company_id == company_id,
                Subscription.status == "active",
                Subscription.plan_code != FREE_PLAN_CODE,
                Subscription.ends_at.is_not(None),
                Subscription.ends_at <= cutoff,
            )
        )
    ).scalars().all()
    if not overdue:
        return {"expired_subs": 0, "paused_stores": [], "revoked_members": []}

    actives = (await db.execute(select(Subscription).where(Subscription.company_id == company_id, Subscription.status == "active"))).scalars().all()
    successor = next((row for row in actives if row.plan_code != FREE_PLAN_CODE and is_in_force(row)), None)
    if successor is not None:
        for subscription in overdue:
            subscription.status = "expired"
            subscription.scheduled_plan_code = None
            subscription.scheduled_store_ids = None
            subscription.scheduled_member_ids = None
        plan = await db.get(Plan, successor.plan_code)
        paused = {"stores": [], "members": []}
        if plan is not None:
            paused = await enforce_plan_capacity(
                db,
                company_id,
                subscription=successor,
                plan=plan,
                keep_store_ids=successor.scheduled_store_ids or [],
                keep_member_ids=successor.scheduled_member_ids or [],
                reason="downgrade",
            )
        successor.scheduled_plan_code = None
        successor.scheduled_store_ids = None
        successor.scheduled_member_ids = None
        return {"expired_subs": len(overdue), "paused_stores": paused["stores"], "revoked_members": paused["members"], "successor_plan": successor.plan_code}

    existing_free = next((row for row in actives if row.plan_code == FREE_PLAN_CODE), None)
    paused_stores: list[str] = []
    revoked_members: list[str] = []
    preferred_store_id = None
    if overdue[0].scheduled_store_ids:
        preferred_store_id = overdue[0].scheduled_store_ids[0]
    for subscription in overdue:
        subscription.status = "expired"
        subscription.scheduled_plan_code = None
        subscription.scheduled_store_ids = None
        subscription.scheduled_member_ids = None
    if existing_free is None:
        free_plan = await _free_plan(db)
        paused_stores = await pause_stores_over_capacity(db, company_id, limit=free_plan.max_stores, preferred_store_id=preferred_store_id)
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
        await db.flush()
        await record_capacity_actions(
            db, subscription=fallback, resource_type="store", resource_ids=paused_stores, action="pause", reason="expiry"
        )
        await record_capacity_actions(
            db, subscription=fallback, resource_type="member", resource_ids=revoked_members, action="pause", reason="expiry"
        )
    return {"expired_subs": len(overdue), "paused_stores": paused_stores, "revoked_members": revoked_members}


async def run_expiry_job(db: AsyncSession) -> dict:
    """Find every company with an overdue paid plan and apply the Free fallback.

    Safe to run repeatedly: once a subscription is marked ``expired`` it is no
    longer selected, and the fallback is only created when none is in force.
    A plan is only overdue once its grace window has fully elapsed.
    """
    cutoff = utc_now() - timedelta(hours=settings.billing_grace_hours)
    overdue = (
        await db.execute(
            select(Subscription).where(
                Subscription.status == "active",
                Subscription.plan_code != FREE_PLAN_CODE,
                Subscription.ends_at.is_not(None),
                Subscription.ends_at <= cutoff,
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
    subscription: Subscription | None = None,
    reason: str = "upgrade",
) -> dict:
    """Re-activate force-paused stores/members up to the in-force plan's limits.

    ``store_ids``/``member_ids`` come from a fallback subscription's paused
    snapshot and are already ordered most-recently-active first, so when the
    new plan cannot fit everyone the most active items return first. When
    ``subscription`` is given, each restore is written to the capacity audit
    trail and the matching pause rows are stamped ``restored_at``.
    """
    restored = {"stores": 0, "members": 0}
    restored_store_ids: list[str] = []
    restored_member_ids: list[str] = []
    active_stores = await db.scalar(select(func.count(Store.id)).where(Store.company_id == company_id, Store.is_active.is_(True)))
    room = plan.max_stores - (active_stores or 0)
    for raw_id in store_ids:
        if room <= 0:
            break
        store = await db.get(Store, UUID(raw_id))
        if store is not None and store.company_id == company_id and not store.is_active:
            store.is_active = True
            restored["stores"] += 1
            restored_store_ids.append(raw_id)
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
            restored_member_ids.append(raw_id)
            room -= 1

    if subscription is not None:
        if restored_store_ids:
            await record_capacity_actions(
                db, subscription=subscription, resource_type="store", resource_ids=restored_store_ids, action="restore", reason=reason
            )
        if restored_member_ids:
            await record_capacity_actions(
                db, subscription=subscription, resource_type="member", resource_ids=restored_member_ids, action="restore", reason=reason
            )
        await _mark_capacity_restored(db, company_id=company_id, resource_type="store", resource_ids=restored_store_ids)
        await _mark_capacity_restored(db, company_id=company_id, resource_type="member", resource_ids=restored_member_ids)
    return restored
