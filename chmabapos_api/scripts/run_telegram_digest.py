import asyncio
import sys

sys.path.insert(0, "chmabapos_api")

from app.db import SessionLocal
from app.services.telegram_digest import run_daily_digest


async def main() -> None:
    async with SessionLocal() as db:
        stats = await run_daily_digest(db)
    print(f"Telegram digest: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
