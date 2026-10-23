"""Freeze the loyalty points a sale awarded.

A full refund must claw back exactly what completion granted. Recomputing from
the store's current rate is wrong after a plan disables loyalty or the rate
changes, so store the award on the order. NULL marks pre-column orders, which
refunds continue to settle with the historical formula.

Revision ID: a3c4d5e6f7b8
Revises: f2b6d4a8c1e9
Create Date: 2026-10-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3c4d5e6f7b8"
down_revision: Union[str, None] = "f2b6d4a8c1e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("loyalty_awarded", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "loyalty_awarded")
