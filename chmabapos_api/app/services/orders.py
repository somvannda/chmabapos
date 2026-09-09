from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Customer, InventoryBalance, Order, Payment, Plan, StockMovement, Store, Subscription


async def ensure_transaction_available(db: AsyncSession, company_id: UUID) -> None:
    """Apply current plan status and transaction quota before a sale is completed."""
    subscription_result = await db.execute(
        select(Subscription)
        .where(Subscription.company_id == company_id, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
    )
    subscription = subscription_result.scalars().first()
    if not subscription:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="An active plan is required to complete sales")
    now = datetime.now(timezone.utc)
    if subscription.ends_at and subscription.ends_at <= now:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your plan has expired")
    plan_result = await db.execute(select(Plan).where(Plan.code == subscription.plan_code, Plan.is_active.is_(True)))
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your plan is unavailable")
    transaction_count = await db.scalar(
        select(func.count(Order.id))
        .join(Store, Store.id == Order.store_id)
        .where(
            Store.company_id == company_id,
            Order.status == "paid",
            Order.created_at >= subscription.starts_at,
            *( [Order.created_at < subscription.ends_at] if subscription.ends_at else [] ),
        )
    )
    if (transaction_count or 0) >= plan.transaction_limit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{plan.name} plan transaction limit reached")


async def complete_order(db: AsyncSession, order_id: UUID, approved_at: datetime | None = None) -> Order:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items), selectinload(Order.payments))
        .with_for_update()
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status == "paid":
        return order
    store_result = await db.execute(select(Store).where(Store.id == order.store_id))
    store = store_result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    await ensure_transaction_available(db, store.company_id)
    for item in order.items:
        balance_result = await db.execute(
            select(InventoryBalance)
            .where(InventoryBalance.store_id == order.store_id, InventoryBalance.product_id == item.product_id)
            .with_for_update()
        )
        balance = balance_result.scalar_one_or_none()
        if not balance or balance.on_hand < item.quantity:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock for {item.product_name}")
        balance.on_hand -= item.quantity
        db.add(
            StockMovement(
                store_id=order.store_id,
                product_id=item.product_id,
                quantity=-item.quantity,
                movement_type="sale",
                reason="completed_order",
                reference_id=order.order_number,
                created_by=order.created_by,
            )
        )
    order.status = "paid"
    order.paid_at = approved_at or datetime.now(timezone.utc)
    for payment in order.payments:
        if payment.status != "paid" or payment.approved_at is None:
            payment.status = "paid"
            payment.approved_at = order.paid_at
    if order.customer_id:
        rate = Decimal(dict(store.preferences or {}).get("loyalty_pts_per_usd", 1))
        if dict(store.preferences or {}).get("loyalty_enabled", True) and rate > 0:
            award = int((order.total - order.tip) * rate)
            if award > 0:
                customer = (await db.execute(select(Customer).where(Customer.id == order.customer_id))).scalar_one_or_none()
                if customer:
                    customer.points = customer.points + award
    return order
