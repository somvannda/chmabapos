"""Shared, variant-aware inventory queries.

Most products track stock directly in ``inventory_balances``. Products that have
variants instead keep it in ``variant_inventory_balances`` — their product-level
row is not the source of truth (it is left at zero). Anything that needs "stock
on hand" or "low stock" therefore has to look at both tables, which is what
these helpers centralise.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InventoryBalance, Product, ProductVariant, VariantInventoryBalance


async def low_stock_items(db: AsyncSession, *, store_id, limit: int | None = None) -> list[dict]:
    """Every product or variant at or below its reorder point, lowest first.

    Variant-tracked products are reported per variant; products without variants
    are reported once. Each item has ``product_id``, ``name`` (product name),
    ``variant_name`` (``None`` for simple products), ``sku``, ``on_hand`` and
    ``reorder_point``. ``on_hand``/``reorder_point`` are ``Decimal`` where the
    balance is numeric.
    """
    no_variants = ~select(ProductVariant.id).where(ProductVariant.product_id == Product.id).exists()
    product_rows = (
        await db.execute(
            select(Product.id, Product.name, Product.sku, InventoryBalance.on_hand, InventoryBalance.reorder_point)
            .join(InventoryBalance, InventoryBalance.product_id == Product.id)
            .where(
                InventoryBalance.store_id == store_id,
                InventoryBalance.on_hand <= InventoryBalance.reorder_point,
                no_variants,
            )
        )
    ).all()
    variant_rows = (
        await db.execute(
            select(
                Product.id,
                Product.name,
                Product.sku,
                ProductVariant.id,
                ProductVariant.name,
                ProductVariant.sku,
                VariantInventoryBalance.on_hand,
                VariantInventoryBalance.reorder_point,
            )
            .join(ProductVariant, ProductVariant.id == VariantInventoryBalance.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(
                VariantInventoryBalance.store_id == store_id,
                VariantInventoryBalance.on_hand <= VariantInventoryBalance.reorder_point,
            )
        )
    ).all()

    items = [
        {
            "product_id": product_id,
            "name": name,
            "variant_name": None,
            "sku": sku,
            "on_hand": on_hand,
            "reorder_point": reorder_point,
        }
        for product_id, name, sku, on_hand, reorder_point in product_rows
    ]
    items += [
        {
            "product_id": product_id,
            "name": name,
            "variant_name": variant_name,
            "sku": variant_sku or product_sku,
            "on_hand": on_hand,
            "reorder_point": reorder_point,
        }
        for product_id, name, product_sku, _variant_id, variant_name, variant_sku, on_hand, reorder_point in variant_rows
    ]
    items.sort(key=lambda item: Decimal(str(item["on_hand"])))
    return items[:limit] if limit else items
