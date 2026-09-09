import asyncio
import sys
from decimal import Decimal

from sqlalchemy import select

sys.path.insert(0, "chmabapos_api")

from app.db import SessionLocal
from app.features import DEFAULT_FEATURES_BY_PLAN
from app.models import Currency, Plan


CURRENCIES = [
    {"code": "USD", "name": "US Dollar", "symbol": "$", "decimal_places": 2},
    {"code": "KHR", "name": "Cambodian Riel", "symbol": "៛", "decimal_places": 0},
    {"code": "THB", "name": "Thai Baht", "symbol": "฿", "decimal_places": 2},
    {"code": "VND", "name": "Vietnamese Dong", "symbol": "₫", "decimal_places": 0},
    {"code": "SGD", "name": "Singapore Dollar", "symbol": "S$", "decimal_places": 2},
]

PLANS = [
    {
        "code": "free",
        "name": "Free",
        "description": "For finding your rhythm.",
        "monthly_price": Decimal("0.00"),
        "max_stores": 1,
        "max_members": 1,
        "transaction_limit": 50,
    },
    {
        "code": "starter",
        "name": "Starter",
        "description": "For teams making moves.",
        "monthly_price": Decimal("1.99"),
        "max_stores": 1,
        "max_members": 5,
        "transaction_limit": 1000,
    },
    {
        "code": "pro",
        "name": "Pro",
        "description": "For stores ready to scale.",
        "monthly_price": Decimal("4.99"),
        "max_stores": 5,
        "max_members": 50,
        "transaction_limit": 10000,
    },
]

for plan in PLANS:
    plan["capabilities"] = {key: key in DEFAULT_FEATURES_BY_PLAN[plan["code"]] for key in DEFAULT_FEATURES_BY_PLAN["pro"]}


async def seed() -> None:
    async with SessionLocal() as db:
        for values in CURRENCIES:
            row = await db.get(Currency, values["code"])
            if row:
                for key, value in values.items():
                    setattr(row, key, value)
            else:
                db.add(Currency(**values))
        for values in PLANS:
            row = await db.get(Plan, values["code"])
            if row:
                for key, value in values.items():
                    setattr(row, key, value)
            else:
                db.add(Plan(**values))
        await db.commit()
    print("Seed complete: currencies and plans")


if __name__ == "__main__":
    asyncio.run(seed())
