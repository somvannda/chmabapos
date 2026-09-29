"""Enqueue the mailing drip, then drain the queue once.

    python chmabapos_api/scripts/run_mailing_drip.py

Intended for a scheduler (hourly is plenty). Safe to run more than once: each
(user, step) is enqueued at most once, and the queue dedupes by due time.
"""
import asyncio
import sys

sys.path.insert(0, "chmabapos_api")

from app.db import SessionLocal
from app.services.mailing import run_mailing_drip, send_pending_emails


async def main() -> None:
    async with SessionLocal() as db:
        drip = await run_mailing_drip(db)
        queue = await send_pending_emails(db)
    print(f"Mailing drip: {drip}")
    print(f"Mailing queue: {queue}")


if __name__ == "__main__":
    asyncio.run(main())
