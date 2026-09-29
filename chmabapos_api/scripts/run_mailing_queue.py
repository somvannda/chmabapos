"""Drain the mailing send queue.

    python chmabapos_api/scripts/run_mailing_queue.py

Intended for a frequent scheduler (every minute is plenty) so queued manual
sends and drip steps go out promptly. Safe to run often: rows are claimed by
due time, retried with backoff, and only leave the queue once sent, exhausted,
or unsubscribed.
"""
import asyncio
import sys

sys.path.insert(0, "chmabapos_api")

from app.db import SessionLocal
from app.services.mailing import send_pending_emails


async def main() -> None:
    async with SessionLocal() as db:
        stats = await send_pending_emails(db)
    print(f"Mailing queue: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
