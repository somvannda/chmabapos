"""point the supplier-prices help article at the control that exists

The article said "open Products, edit a product and choose Supplier prices".
That control never existed in the edit form - the entry point is a dollar icon
on the product row - so a merchant following the steps found nothing and
concluded the feature was missing. The row is edited through the admin help
editor, so the fix has to land in ``help_articles``, not only in the static
fallback in ``app/support_content.py``.

Revision ID: c7f2e9a4d1b8
Revises: b3d7f1a9c2e5
Create Date: 2026-11-04

"""
from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "c7f2e9a4d1b8"
down_revision: str | None = "b3d7f1a9c2e5"
branch_labels = None
depends_on = None

ARTICLE_ID = "products.supplier-prices"

# The wording this replaces, kept so the migration can be reversed.
PREVIOUS_STEPS = [
    "Open Products, edit a product and choose Supplier prices.",
    "Add a supplier with their cost price, supplier SKU, lead time and minimum order.",
    "Mark one supplier as preferred.",
    "Use these costs when you create purchase orders.",
]
PREVIOUS_STEPS_KM = [
    "បើក ទំនិញ កែទំនិញ ហើយជ្រើស តម្លៃអ្នកផ្គត់ផ្គង់។",
    "បន្ថែមអ្នកផ្គត់ផ្គង់ជាមួយតម្លៃដើម SKU របស់អ្នកផ្គត់ផ្គង់ រយៈពេលដឹកជញ្ជូន និងចំនួនអប្បបរមា។",
    "សម្គាល់អ្នកផ្គត់ផ្គង់ម្នាក់ជាចម្បង។",
    "ប្រើតម្លៃទាំងនេះនៅពេលបង្កើតការបញ្ជាទិញទំនិញ។",
]


def _table() -> sa.TableClause:
    return sa.table(
        "help_articles",
        sa.column("id", sa.String),
        sa.column("steps", sa.JSON),
        sa.column("steps_km", sa.JSON),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )


def _current_steps() -> tuple[list[str] | None, list[str] | None]:
    """The corrected text, read from the seed module so the two cannot drift."""
    from app import support_content

    for section in support_content.SUPPORT_SECTIONS:
        for article in section["articles"]:
            if article["id"] == ARTICLE_ID:
                translated = support_content.KH_TRANSLATIONS.get(ARTICLE_ID, {})
                return article["steps"], translated.get("steps")
    return None, None


def upgrade() -> None:
    steps, steps_km = _current_steps()
    if steps is None:
        return
    table = _table()
    op.execute(
        table.update()
        .where(table.c.id == ARTICLE_ID)
        .values(steps=steps, steps_km=steps_km, updated_at=datetime.now(timezone.utc))
    )


def downgrade() -> None:
    table = _table()
    op.execute(
        table.update()
        .where(table.c.id == ARTICLE_ID)
        .values(steps=PREVIOUS_STEPS, steps_km=PREVIOUS_STEPS_KM, updated_at=datetime.now(timezone.utc))
    )
