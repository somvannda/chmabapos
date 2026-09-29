"""Run the mailing drip. Intended for a scheduler (e.g. hourly or daily).

    python chmabapos_api/scripts/run_mailing_drip.py

Safe to run more than once: each (user, step) is delivered at most once.
"""
import asyncio
import sys

sys.path.insert(0, "chmabapos_api")

from app.db import SessionLocal
from app.services.mailing import run_mailing_drip


async def main() -> None:
    async with SessionLocal() as db:
        stats = await run_mailing_drip(db)
    print(f"Mailing drip: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
