"""Read-only store data tools for the support assistant.

The assistant normally answers "how do I" questions from the help corpus. These
tools add "what is / how much" answers about the caller's *own* store by running a
small, fixed set of tenant-scoped queries.

They are deliberately not a general SQL surface: only the functions defined here
run, every one is scoped to a single store, and results are size-capped. The
assistant never supplies raw SQL or table names.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InventoryBalance, Order, Product

MAX_ROWS = 10


async def low_stock(db: AsyncSession, *, store_id, limit: int = MAX_ROWS) -> list[dict[str, Any]]:
    """Products at or below their reorder point in this store, lowest first."""
    rows = (
        await db.execute(
            select(Product.name, Product.sku, InventoryBalance.on_hand, InventoryBalance.reorder_point)
            .join(InventoryBalance, InventoryBalance.product_id == Product.id)
            .where(InventoryBalance.store_id == store_id, InventoryBalance.on_hand <= InventoryBalance.reorder_point)
            .order_by(InventoryBalance.on_hand)
            .limit(limit)
        )
    ).all()
    return [{"name": name, "sku": sku, "on_hand": str(on_hand), "reorder_point": reorder} for name, sku, on_hand, reorder in rows]


async def find_products(db: AsyncSession, *, company_id, store_id, term: str, limit: int = MAX_ROWS) -> list[dict[str, Any]]:
    """Products whose name matches ``term``, with on-hand for this store."""
    like = f"%{term.strip()}%"
    rows = (
        await db.execute(
            select(Product.name, Product.sku, Product.price, InventoryBalance.on_hand)
            .outerjoin(InventoryBalance, (InventoryBalance.product_id == Product.id) & (InventoryBalance.store_id == store_id))
            .where(Product.company_id == company_id, Product.is_active.is_(True), Product.name.ilike(like))
            .order_by(Product.name)
            .limit(limit)
        )
    ).all()
    return [
        {"name": name, "sku": sku, "price": str(price), "on_hand": (str(on_hand) if on_hand is not None else None)}
        for name, sku, price, on_hand in rows
    ]


async def sales_summary(db: AsyncSession, *, store_id, days: int = 1) -> dict[str, Any]:
    """Paid transactions and total for the last ``days`` in this store."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    count, total = (
        await db.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0)).where(
                Order.store_id == store_id,
                Order.status == "paid",
                Order.created_at >= since,
            )
        )
    ).one()
    currency = await db.scalar(
        select(Order.currency_code)
        .where(Order.store_id == store_id, Order.status == "paid")
        .order_by(Order.created_at.desc())
        .limit(1)
    )
    return {"transactions": int(count or 0), "total": str(total or "0"), "currency": currency or "USD", "days": days}
