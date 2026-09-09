import asyncio
import sys

sys.path.insert(0, "chmabapos_api")

from app.db import SessionLocal
from app.services.billing_lifecycle import run_expiry_job


async def main() -> None:
    async with SessionLocal() as db:
        stats = await run_expiry_job(db)
        await db.commit()
    print(f"Billing expiry job complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
