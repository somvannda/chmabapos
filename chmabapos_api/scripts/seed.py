import asyncio
import sys
from decimal import Decimal

from sqlalchemy import select

sys.path.insert(0, "chmabapos_api")

from app.config import settings
from app.db import SessionLocal
from app.features import DEFAULT_FEATURES_BY_PLAN
from app.models import Currency, EmailTemplate, Plan
from app.services.onboarding_emails import BASE_TOKEN, ONBOARDING_EMAILS


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
        "transaction_limit": 3000,
    },
    {
        "code": "starter",
        "name": "Starter",
        "description": "For teams making moves.",
        "monthly_price": Decimal("0.99"),
        "max_stores": 5,
        "max_members": 10,
        "transaction_limit": 15000,
    },
    {
        "code": "pro",
        "name": "Pro",
        "description": "For stores ready to scale.",
        "monthly_price": Decimal("4.99"),
        "max_stores": 50,
        "max_members": 99,
        "transaction_limit": 1000000,
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
        # Mirror the automated onboarding sequence as editable mailing templates
        # so an operator can review, tweak and manually send the same copy. A
        # template is only inserted once (matched on its name), so later edits in
        # the admin Mailing tool are never overwritten by a restart.
        existing_templates = set((await db.execute(select(EmailTemplate.name))).scalars().all())
        base = settings.frontend_url.rstrip("/")
        added_templates = 0
        for email in ONBOARDING_EMAILS:
            name = str(email["name"])
            if name in existing_templates:
                continue
            db.add(
                EmailTemplate(
                    name=name,
                    subject=str(email["subject"]),
                    body_html=str(email["body_html"]).replace(BASE_TOKEN, base),
                )
            )
            added_templates += 1
        await db.commit()
    print(f"Seed complete: currencies, plans and {added_templates} onboarding template(s)")


if __name__ == "__main__":
    asyncio.run(seed())
