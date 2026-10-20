"""Freeze each order's rate to the company base currency.

Every report converts into the company's base currency. That conversion was
re-derived from the rate table at the order's date, so editing or backfilling a
rate silently rewrote past revenue. Freezing the rate with the sale makes a
re-run of the same period return the same number.

Additive and nullable: existing orders keep the table fallback (and a later
backfill could fill them in), and USD/company-base orders store 1.

Revision ID: e7d9c1b3a5f2
Revises: f9a1c3e5b7d2
Create Date: 2026-10-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7d9c1b3a5f2"
down_revision: Union[str, None] = "f9a1c3e5b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("company_base_rate", sa.Numeric(20, 8), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "company_base_rate")
