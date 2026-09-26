import asyncio
import sys

sys.path.insert(0, "chmabapos_api")

from app.db import SessionLocal
from app.api.v1 import reconcile_open_order_payments, reconcile_pending_billing_payments
from app.services.billing_lifecycle import run_expiry_job
from app.services.reminders import run_reminder_job


async def main() -> None:
    async with SessionLocal() as db:
        # Reconcile first: a payment that settled without a webhook should
        # activate the plan before the expiry job considers it overdue.
        billing_reconcile = await reconcile_pending_billing_payments(db)
        order_reconcile = await reconcile_open_order_payments(db)
        expiry = await run_expiry_job(db)
        reminders = await run_reminder_job(db)
        await db.commit()
    print(f"Payment reconcile (billing): {billing_reconcile}")
    print(f"Payment reconcile (orders): {order_reconcile}")
    print(f"Billing expiry job: {expiry}")
    print(f"Billing reminders: {reminders}")


if __name__ == "__main__":
    asyncio.run(main())
