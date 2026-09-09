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
        "marketing_features": [
            "1 store",
            "1 owner account",
            "Basic POS with cash & card",
            "50 transactions per month",
            "Weekly sales reports",
            "Customer management",
        ],
    },
    {
        "code": "starter",
        "name": "Starter",
        "description": "For teams making moves.",
        "monthly_price": Decimal("1.99"),
        "max_stores": 1,
        "max_members": 5,
        "transaction_limit": 1000,
        "marketing_features": [
            "1 store",
            "Up to 5 team members",
            "1,000 transactions per month",
            "Full inventory management",
            "KHQR & multi-currency payments",
            "Advanced reports & GDT export",
            "Customer loyalty points",
            "Barcode scanning",
            "Shift management",
            "Email receipts",
            "Purchase orders & suppliers",
            "Refunds & held orders",
        ],
    },
    {
        "code": "pro",
        "name": "Pro",
        "description": "For stores ready to scale.",
        "monthly_price": Decimal("4.99"),
        "max_stores": 5,
        "max_members": 50,
        "transaction_limit": 10000,
        "marketing_features": [
            "Up to 5 stores",
            "Up to 50 team members",
            "10,000 transactions per month",
            "Multi-store reporting & consolidated sales",
            "Full inventory management",
            "Suppliers & purchase orders",
            "KHQR & online payments",
            "Multi-currency & exchange rates",
            "Advanced reports & GDT export",
            "Customer loyalty points",
            "Barcode scanning",
            "Shift management",
            "Email receipts",
            "Refunds & held orders",
            "Custom receipt templates",
            "Roles & permissions",
            "Priority support",
        ],
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
