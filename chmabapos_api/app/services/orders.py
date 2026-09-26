from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.billing import grace_deadline, load_entitlement
from app.models import Customer, InventoryBalance, Order, Payment, ProductBatch, ProductSerial, StockMovement, Store, VariantInventoryBalance
from app.services.activity import record_activity


async def ensure_transaction_available(db: AsyncSession, company_id: UUID) -> None:
    """Apply the effective plan's status and transaction quota before a sale completes.

    ``load_entitlement`` resolves the in-force subscription (or Free fallback),
    so an expired paid plan no longer grants paid entitlements and never lets a
    sale through under a stale plan.

    The counting window ends at the subscription's grace deadline, not at
    ``ends_at``: a plan stays in force through the grace window, so sales taken
    during grace must still count against the same quota. A Free plan (no
    ``ends_at``) is open-ended.
    """
    ent = await load_entitlement(db, company_id)
    subscription = ent.subscription
    if not subscription:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ent.denied_reason(action="complete sales"))
    plan = ent.plan
    window_end = grace_deadline(subscription) or datetime.now(timezone.utc)
    transaction_count = await db.scalar(
        select(func.count(Order.id))
        .join(Store, Store.id == Order.store_id)
        .where(
            Store.company_id == company_id,
            Order.status == "paid",
            Order.created_at >= subscription.starts_at,
            Order.created_at < window_end,
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
        if item.variant_id:
            balance_result = await db.execute(
                select(VariantInventoryBalance)
                .where(VariantInventoryBalance.store_id == order.store_id, VariantInventoryBalance.variant_id == item.variant_id)
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
                    variant_id=item.variant_id,
                    quantity=-item.quantity,
                    movement_type="sale",
                    reason="completed_order",
                    reference_id=order.order_number,
                    created_by=order.created_by,
                )
            )
        else:
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
        serials = (await db.execute(select(ProductSerial).where(ProductSerial.order_item_id == item.id, ProductSerial.status == "in_stock"))).scalars().all()
        for serial in serials:
            serial.status = "sold"
        for entry in (item.modifiers or []):
            ingredient_id = entry.get("ingredient_product_id")
            if not ingredient_id:
                continue
            ingredient_quantity = int(entry.get("ingredient_quantity", 1)) * item.quantity
            ingredient_balance_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == order.store_id, InventoryBalance.product_id == UUID(ingredient_id)).with_for_update())
            ingredient_balance = ingredient_balance_result.scalar_one_or_none()
            if ingredient_balance:
                ingredient_balance.on_hand -= ingredient_quantity
                db.add(StockMovement(store_id=order.store_id, product_id=UUID(ingredient_id), quantity=-ingredient_quantity, movement_type="sale", reason="modifier_recipe", reference_id=order.order_number, created_by=order.created_by))
        remaining = item.quantity
        batches = (await db.execute(select(ProductBatch).where(ProductBatch.company_id == store.company_id, ProductBatch.product_id == item.product_id, ProductBatch.variant_id == item.variant_id, ProductBatch.store_id == order.store_id, ProductBatch.quantity_on_hand > 0).order_by(ProductBatch.expiry_date.asc().nulls_last(), ProductBatch.created_at))).scalars().all()
        for batch in batches:
            if remaining <= 0:
                break
            take = min(batch.quantity_on_hand, remaining)
            batch.quantity_on_hand -= take
            remaining -= take
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
    await record_activity(db, "order.paid", company_id=store.company_id, store_id=order.store_id, details={"store": store.name, "order_number": order.order_number, "amount": f"{order.total} {order.currency_code}"})
    return order
