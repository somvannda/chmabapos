import asyncio
import sys

sys.path.insert(0, "chmabapos_api")

from app.db import SessionLocal
from app.services.billing_lifecycle import run_expiry_job
from app.services.reminders import run_reminder_job


async def main() -> None:
    async with SessionLocal() as db:
        expiry = await run_expiry_job(db)
        reminders = await run_reminder_job(db)
        await db.commit()
    print(f"Billing expiry job: {expiry}")
    print(f"Billing reminders: {reminders}")


if __name__ == "__main__":
    asyncio.run(main())
