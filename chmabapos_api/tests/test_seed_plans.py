"""Seeded plans are defaults, not a reset button on every API start."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.db import SessionLocal
from app.models import Plan
from scripts.seed import seed


@pytest.mark.asyncio
async def test_seed_does_not_overwrite_an_edited_plan() -> None:
    async with SessionLocal() as db:
        plan = await db.get(Plan, "starter")
        assert plan is not None
        original = plan.monthly_price
        plan.monthly_price = Decimal("12.34")
        await db.commit()
    try:
        await seed()
        async with SessionLocal() as db:
            plan = await db.get(Plan, "starter")
            assert plan is not None
            assert plan.monthly_price == Decimal("12.34")
    finally:
        async with SessionLocal() as db:
            plan = await db.get(Plan, "starter")
            if plan is not None:
                plan.monthly_price = original
                await db.commit()
