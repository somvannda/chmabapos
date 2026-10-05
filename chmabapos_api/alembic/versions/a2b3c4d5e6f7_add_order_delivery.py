"""add_order_delivery

Revision ID: a2b3c4d5e6f7
Revises: f9e8d7c6b5a4
Create Date: 2026-10-05 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'a2b4c6d8e0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('delivery_status', sa.String(length=20), server_default='none', nullable=False))
    op.add_column('orders', sa.Column('driver_name', sa.String(length=120), nullable=True))
    op.add_column('orders', sa.Column('delivery_address', sa.String(length=400), nullable=True))
    op.add_column('orders', sa.Column('delivery_notes', sa.Text(), nullable=True))
    op.add_column('orders', sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'delivered_at')
    op.drop_column('orders', 'assigned_at')
    op.drop_column('orders', 'delivery_notes')
    op.drop_column('orders', 'delivery_address')
    op.drop_column('orders', 'driver_name')
    op.drop_column('orders', 'delivery_status')
