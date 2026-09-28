"""add_cost_snapshot

Revision ID: c5e7f9a1b3d2
Revises: b4d6e8f0a2c3
Create Date: 2026-09-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5e7f9a1b3d2'
down_revision: Union[str, None] = 'b4d6e8f0a2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stock_movements', sa.Column('unit_cost', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('order_items', sa.Column('cost_price', sa.Numeric(precision=12, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('order_items', 'cost_price')
    op.drop_column('stock_movements', 'unit_cost')
