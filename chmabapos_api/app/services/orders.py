from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.billing import grace_deadline, load_entitlement
from app.models import Customer, InventoryBalance, Order, OrderItem, Payment, Product, ProductBatch, ProductSerial, ProductVariant, StockMovement, Store, VariantInventoryBalance
from app.services.activity import record_activity
from app.services.sale_emails import queue_sale_emails

logger = logging.getLogger(__name__)


async def weighted_average_cost(db: AsyncSession, store_id: UUID, product_id: UUID, variant_id: UUID | None) -> Decimal | None:
    """Average per-unit cost of costed inflows for a store product/variant.

    Only positive-quantity movements that carry a ``unit_cost`` count, so sales
    and uncosted adjustments do not distort the basis. Returns ``None`` when no
    costed receipt exists yet, letting callers fall back to catalog cost.
    """
    conditions = [
        StockMovement.store_id == store_id,
        StockMovement.product_id == product_id,
        StockMovement.quantity > 0,
        StockMovement.unit_cost.is_not(None),
    ]
    if variant_id:
        conditions.append(StockMovement.variant_id == variant_id)
    else:
        conditions.append(StockMovement.variant_id.is_(None))
    total_quantity, total_cost = (await db.execute(select(func.sum(StockMovement.quantity), func.sum(StockMovement.quantity * StockMovement.unit_cost)).where(*conditions))).one()
    if total_quantity and total_quantity > 0 and total_cost is not None:
        return (Decimal(total_cost) / Decimal(total_quantity)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return None


async def resolve_order_item_unit_cost(db: AsyncSession, order: Order, item: OrderItem) -> Decimal | None:
    """Best-known per-unit cost for an order line at fulfillment time.

    Serial units carry their own receipt cost; otherwise use the weighted
    average of costed receipts, then fall back to the variant/product catalog
    cost. ``None`` means "unknown" and is left for the margin report to resolve.
    """
    serials = list(item.serials or [])
    serial_costs = [serial.cost_price for serial in serials if serial.cost_price is not None]
    if serials and len(serial_costs) == len(serials) and item.quantity:
        return (sum(serial_costs, Decimal("0")) / Decimal(item.quantity)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    average = await weighted_average_cost(db, order.store_id, item.product_id, item.variant_id)
    if average is not None:
        return average
    if item.variant_id:
        variant_cost = await db.scalar(select(ProductVariant.cost_price).where(ProductVariant.id == item.variant_id))
        if variant_cost is not None:
            return variant_cost
    return await db.scalar(select(Product.cost_price).where(Product.id == item.product_id))


async def _component_unit_cost(db: AsyncSession, store_id: UUID, product_id: UUID, variant_id: UUID | None) -> Decimal | None:
    """Best-known per-unit cost for a single combo component."""
    average = await weighted_average_cost(db, store_id, product_id, variant_id)
    if average is not None:
        return average
    if variant_id:
        variant_cost = await db.scalar(select(ProductVariant.cost_price).where(ProductVariant.id == variant_id))
        if variant_cost is not None:
            return variant_cost
    return await db.scalar(select(Product.cost_price).where(Product.id == product_id))


async def resolve_combo_unit_cost(db: AsyncSession, order: Order, item: OrderItem) -> Decimal | None:
    """Per-combo cost basis: the summed cost of its components at fulfilment.

    ``None`` means every component's cost is unknown; the margin report then
    treats the line cost as unresolved rather than zero.
    """
    total = Decimal("0")
    known = False
    for component in (item.combo_components or []):
        product_id = UUID(component["product_id"])
        variant_id = UUID(component["variant_id"]) if component.get("variant_id") else None
        quantity = Decimal(str(component.get("quantity", "1")))
        cost = await _component_unit_cost(db, order.store_id, product_id, variant_id)
        if cost is not None:
            known = True
            total += cost * quantity
    if not known:
        return None
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def _deplete_component(db: AsyncSession, order: Order, company_id: UUID, product_id: UUID, variant_id: UUID | None, quantity: Decimal, *, deplete_balance: bool = True) -> None:
    """Draw one combo component down: balance, movement, then FEFO batches.

    ``deplete_balance=False`` is used for a reservation whose stock was already
    held at deposit time: the shelf balance must not be reduced twice, but the
    batch consumption still happens at collection so FEFO tracks the sale.
    """
    if deplete_balance:
        if variant_id:
            balance = (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == order.store_id, VariantInventoryBalance.variant_id == variant_id).with_for_update())).scalar_one_or_none()
        else:
            balance = (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == order.store_id, InventoryBalance.product_id == product_id).with_for_update())).scalar_one_or_none()
        if not balance or balance.on_hand < quantity:
            name = await db.scalar(select(Product.name).where(Product.id == product_id))
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock for {name}")
        balance.on_hand -= quantity
        db.add(StockMovement(store_id=order.store_id, product_id=product_id, variant_id=variant_id, quantity=-quantity, movement_type="sale", reason="combo_sale", reference_id=order.order_number, created_by=order.created_by))
    remaining = quantity
    batches = (
        await db.execute(
            select(ProductBatch)
            .where(
                ProductBatch.company_id == company_id,
                ProductBatch.product_id == product_id,
                ProductBatch.variant_id == variant_id,
                ProductBatch.store_id == order.store_id,
                ProductBatch.quantity_on_hand > 0,
            )
            .order_by(ProductBatch.expiry_date.asc().nulls_last(), ProductBatch.created_at)
        )
    ).scalars().all()
    for batch in batches:
        if remaining <= 0:
            break
        take = min(batch.quantity_on_hand, remaining)
        batch.quantity_on_hand -= take
        remaining -= take


async def deplete_combo_components(db: AsyncSession, order: Order, item: OrderItem, store: Store, *, deplete_balance: bool = True) -> None:
    """A combo is logical: its components carry the stock (docs/combos-plan.md)."""
    for component in (item.combo_components or []):
        product_id = UUID(component["product_id"])
        variant_id = UUID(component["variant_id"]) if component.get("variant_id") else None
        quantity = Decimal(str(component.get("quantity", "1"))) * item.quantity
        await _deplete_component(db, order, store.company_id, product_id, variant_id, quantity, deplete_balance=deplete_balance)


async def _hold_component(db: AsyncSession, order: Order, product_id: UUID, variant_id: UUID | None, quantity: Decimal) -> None:
    """Draw a reservation line off the shelf without recording it as a sale."""
    if variant_id:
        balance = (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == order.store_id, VariantInventoryBalance.variant_id == variant_id).with_for_update())).scalar_one_or_none()
    else:
        balance = (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == order.store_id, InventoryBalance.product_id == product_id).with_for_update())).scalar_one_or_none()
    if not balance or balance.on_hand < quantity:
        name = await db.scalar(select(Product.name).where(Product.id == product_id))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock for {name}")
    balance.on_hand -= quantity
    db.add(StockMovement(store_id=order.store_id, product_id=product_id, variant_id=variant_id, quantity=-quantity, movement_type="reservation", reason="reservation_hold", reference_id=order.order_number, created_by=order.created_by))


async def hold_order_stock(db: AsyncSession, order: Order) -> None:
    """Reserve inventory for a deposit order so it cannot be sold twice.

    Balance is reduced now; batches are left untouched and consumed when the
    reservation is collected. Modifier ingredients are not held because they are
    only consumed when the item is actually made.
    """
    for item in order.items:
        if item.combo_components:
            for component in item.combo_components:
                product_id = UUID(component["product_id"])
                variant_id = UUID(component["variant_id"]) if component.get("variant_id") else None
                quantity = Decimal(str(component.get("quantity", "1"))) * item.quantity
                await _hold_component(db, order, product_id, variant_id, quantity)
            continue
        await _hold_component(db, order, item.product_id, item.variant_id, item.quantity)


async def _release_component(db: AsyncSession, order: Order, product_id: UUID, variant_id: UUID | None, quantity: Decimal, reason: str) -> None:
    """Return a held reservation line to the shelf."""
    if variant_id:
        balance = (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == order.store_id, VariantInventoryBalance.variant_id == variant_id).with_for_update())).scalar_one_or_none()
        if not balance:
            balance = VariantInventoryBalance(store_id=order.store_id, variant_id=variant_id, on_hand=Decimal("0"), reorder_point=10)
            db.add(balance)
            await db.flush()
    else:
        balance = (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == order.store_id, InventoryBalance.product_id == product_id).with_for_update())).scalar_one_or_none()
        if not balance:
            balance = InventoryBalance(store_id=order.store_id, product_id=product_id, on_hand=Decimal("0"), reorder_point=10)
            db.add(balance)
            await db.flush()
    balance.on_hand += quantity
    db.add(StockMovement(store_id=order.store_id, product_id=product_id, variant_id=variant_id, quantity=quantity, movement_type="reservation_release", reason=reason, reference_id=order.order_number, created_by=order.created_by))


async def release_order_stock(db: AsyncSession, order: Order, reason: str) -> None:
    """Undo ``hold_order_stock`` when a reservation is cancelled or expires."""
    for item in order.items:
        if item.combo_components:
            for component in item.combo_components:
                product_id = UUID(component["product_id"])
                variant_id = UUID(component["variant_id"]) if component.get("variant_id") else None
                quantity = Decimal(str(component.get("quantity", "1"))) * item.quantity
                await _release_component(db, order, product_id, variant_id, quantity, reason)
            continue
        await _release_component(db, order, item.product_id, item.variant_id, item.quantity, reason)
    item_ids = [item.id for item in (order.items or [])]
    if not item_ids:
        return
    serials = (await db.execute(select(ProductSerial).where(ProductSerial.order_item_id.in_(item_ids), ProductSerial.status == "reserved"))).scalars().all()
    for serial in serials:
        serial.status = "in_stock"
        serial.order_item_id = None


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
        .options(selectinload(Order.items), selectinload(Order.payments), selectinload(Order.tenders), selectinload(Order.customer))
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
    completed_at = approved_at or datetime.now(timezone.utc)
    for item in order.items:
        # Freeze the cost basis on the sale line so later catalog cost edits
        # cannot rewrite this order's margin.
        if item.combo_components:
            item.cost_price = await resolve_combo_unit_cost(db, order, item)
            await deplete_combo_components(db, order, item, store, deplete_balance=not order.stock_held)
            continue
        item.cost_price = await resolve_order_item_unit_cost(db, order, item)
        if not order.stock_held:
            # A reservation already drew the balance down at deposit time; only
            # batch consumption and serial transitions remain for collection.
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
                        unit_cost=item.cost_price,
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
                        unit_cost=item.cost_price,
                        created_by=order.created_by,
                    )
                )
        serials = (await db.execute(select(ProductSerial).where(ProductSerial.order_item_id == item.id, ProductSerial.status.in_(["in_stock", "reserved"])))).scalars().all()
        for serial in serials:
            serial.status = "sold"
            # The customer warranty clock starts at the moment of sale, not at
            # the moment the unit was received from the supplier.
            serial.sold_at = completed_at
            if serial.customer_warranty_months:
                serial.customer_warranty_until = completed_at + timedelta(days=30 * serial.customer_warranty_months)
        # Snapshot the unit grade onto the line when every sold serial agrees on
        # one grade (the usual one-serial-per-line case). Mixed-grade lines keep
        # the per-unit grades on the serials and leave the line grade empty.
        sold_grades = {serial.condition_grade for serial in serials if serial.condition_grade}
        if len(sold_grades) == 1:
            item.condition_grade = sold_grades.pop()
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
    order.paid_at = completed_at
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
    # Queue the optional owner alert / customer receipt. The rows ride the
    # caller's transaction and the mailing worker delivers them, so nothing here
    # touches the network. A failure must never break the sale.
    try:
        await queue_sale_emails(db, order, store)
    except Exception:
        logger.exception("sale emails could not be queued for order %s", order.order_number)
    return order
