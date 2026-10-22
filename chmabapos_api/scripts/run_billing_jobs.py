import asyncio
import sys

sys.path.insert(0, "chmabapos_api")

from sqlalchemy import func, select

from app.db import SessionLocal, engine
from app.api.v1 import expire_unpaid_online_orders, reconcile_open_held_order_payments, reconcile_open_order_payments, reconcile_pending_billing_payments
from app.services.billing_lifecycle import BILLING_JOB_LOCK_KEY, reconcile_effective_capacity, run_expiry_job
from app.services.reminders import run_reminder_job


async def main() -> None:
    # The in-process worker uses the same lock; skip instead of racing it.
    async with engine.connect() as lock_conn:
        acquired = await lock_conn.scalar(select(func.pg_try_advisory_xact_lock(BILLING_JOB_LOCK_KEY)))
        if not acquired:
            print("Another billing cycle is running; skipped.")
            return
        async with SessionLocal() as db:
            # Reconcile first: a payment that settled without a webhook should
            # activate the plan before the expiry job considers it overdue.
            billing_reconcile = await reconcile_pending_billing_payments(db)
            order_reconcile = await reconcile_open_order_payments(db)
            held_order_reconcile = await reconcile_open_held_order_payments(db)
            expiry = await run_expiry_job(db)
            capacity = await reconcile_effective_capacity(db)
            reminders = await run_reminder_job(db)
            # Last, so an order whose payment settled in the reconcile above is already paid and
            # cannot be expired out from under it.
            expired = await expire_unpaid_online_orders(db)
            await db.commit()
    print(f"Payment reconcile (billing): {billing_reconcile}")
    print(f"Payment reconcile (orders): {order_reconcile}")
    print(f"Payment reconcile (online orders): {held_order_reconcile}")
    print(f"Billing expiry job: {expiry}")
    print(f"Billing capacity: {capacity}")
    print(f"Billing reminders: {reminders}")
    print(f"Unpaid online orders expired: {expired}")


if __name__ == "__main__":
    asyncio.run(main())
