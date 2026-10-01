from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.db import SessionLocal
from app.models import Company, InventoryBalance, Product, Store
from app.services import support


def test_build_prompt_injects_live_data() -> None:
    system, _messages, _guides = support.build_prompt(
        question="How much stock is left?",
        history=[],
        vertical="general",
        role="owner",
        live_data="Items at or below their reorder point:\n- Test Widget (SKU W1): 2 on hand, reorder at 10",
    )
    assert "LIVE STORE DATA" in system
    assert "Test Widget" in system


@pytest.mark.asyncio
async def test_collect_live_data_uses_store_and_ignores_non_data_questions() -> None:
    async with SessionLocal() as db:
        company = Company(name=f"Tools {uuid.uuid4().hex[:6]}", default_currency_code="USD")
        db.add(company)
        await db.flush()
        store = Store(company_id=company.id, name="Main", currency_code="USD")
        db.add(store)
        await db.flush()
        product = Product(company_id=company.id, name="Test Widget", sku=f"W-{uuid.uuid4().hex[:6]}", price=Decimal("5.00"))
        db.add(product)
        await db.flush()
        db.add(InventoryBalance(store_id=store.id, product_id=product.id, on_hand=Decimal("2"), reorder_point=10))
        await db.commit()
        company_id, store_id, product_id, sku = company.id, store.id, product.id, product.sku

    try:
        async with SessionLocal() as db:
            block = await support.collect_live_data(db, question="How much stock of the widget is left?", store_id=store_id, company_id=company_id)
            assert block and "Test Widget" in block and "reorder" in block

            # A specific SKU is looked up directly.
            sku_block = await support.collect_live_data(db, question=f"How many of SKU-{sku} are left?", store_id=store_id, company_id=company_id)
            assert sku_block and "Matching products" in sku_block and "Test Widget" in sku_block

            # An ordinary how-to question is not treated as a data request.
            assert await support.collect_live_data(db, question="How do I open a shift?", store_id=store_id, company_id=company_id) is None

            # Sales intent is recognised even with no orders yet.
            sales = await support.collect_live_data(db, question="What were today's sales?", store_id=store_id, company_id=company_id)
            assert sales and "paid transactions" in sales
    finally:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM inventory_balances WHERE store_id = :store_id"), {"store_id": store_id})
            await db.execute(text("DELETE FROM products WHERE id = :product_id"), {"product_id": product_id})
            await db.execute(text("DELETE FROM stores WHERE id = :store_id"), {"store_id": store_id})
            await db.execute(text("DELETE FROM companies WHERE id = :company_id"), {"company_id": company_id})
            await db.commit()
