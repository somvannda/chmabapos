"""add_order_type

Revision ID: a0b1c2d3e4f5
Revises: c2e3f4a5b6d7
Create Date: 2026-10-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a0b1c2d3e4f5'
down_revision: Union[str, None] = 'c2e3f4a5b6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Default 'takeaway' so every existing row keeps its current "pay and go"
    # meaning; the column is not nullable and the server default stays as a
    # safety net for any writer that omits the field.
    op.add_column('orders', sa.Column('order_type', sa.String(length=20), nullable=False, server_default='takeaway'))
    op.add_column('held_orders', sa.Column('order_type', sa.String(length=20), nullable=False, server_default='takeaway'))


def downgrade() -> None:
    op.drop_column('held_orders', 'order_type')
    op.drop_column('orders', 'order_type')
