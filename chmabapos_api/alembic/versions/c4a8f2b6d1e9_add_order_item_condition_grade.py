"""add_order_item_condition_grade

Snapshot the cosmetic grade of the sold unit(s) onto the order line so receipts
and margin-by-grade reporting keep the historical grade even if the serial is
later re-graded.

Revision ID: c4a8f2b6d1e9
Revises: b7d1e4c9a2f3
Create Date: 2026-09-30 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4a8f2b6d1e9'
down_revision: Union[str, None] = 'b7d1e4c9a2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('order_items', sa.Column('condition_grade', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('order_items', 'condition_grade')
