"""One billing cycle at a time, even with several API workers."""
import pytest
from sqlalchemy import func, select

import app.main as main_module
from app.db import SessionLocal
from app.main import _billing_cycle_once
from app.services.billing_lifecycle import BILLING_JOB_LOCK_KEY


@pytest.mark.asyncio
async def test_billing_cycle_skips_when_another_worker_holds_the_lock(monkeypatch) -> None:
    async with SessionLocal() as blocker:
        held = await blocker.scalar(select(func.pg_try_advisory_xact_lock(BILLING_JOB_LOCK_KEY)))
        assert held is True
        # The worker must not start a second concurrent cycle.
        assert await _billing_cycle_once() is None
        await blocker.rollback()

    async def noop(_db):
        return {}

    for name in (
        "reconcile_pending_billing_payments",
        "reconcile_open_order_payments",
        "reconcile_open_held_order_payments",
        "run_expiry_job",
        "run_reminder_job",
        "expire_unpaid_online_orders",
    ):
        monkeypatch.setattr(main_module, name, noop)

    # A skipped cycle must release its lock for the next worker.
    stats = await _billing_cycle_once()
    assert stats is not None
    assert stats["billing"] == {}
