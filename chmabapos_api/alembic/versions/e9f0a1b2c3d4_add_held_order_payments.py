"""add_held_order_payments

Revision ID: e9f0a1b2c3d4
Revises: f6a1b2c3d4e5
Create Date: 2026-10-04 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e9f0a1b2c3d4'
down_revision: Union[str, None] = 'f6a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('held_orders', sa.Column('payment_status', sa.String(length=20), nullable=False, server_default='unpaid'))
    op.add_column('held_orders', sa.Column('payment_provider', sa.String(length=30), nullable=True))
    op.add_column('held_orders', sa.Column('payment_external_id', sa.String(length=255), nullable=True))
    op.add_column('held_orders', sa.Column('payment_qr_string', sa.Text(), nullable=True))
    op.add_column('held_orders', sa.Column('payment_checkout_url', sa.String(length=500), nullable=True))
    op.add_column('held_orders', sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_held_order_payment_external_id', 'held_orders', ['payment_external_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_held_order_payment_external_id', table_name='held_orders')
    op.drop_column('held_orders', 'paid_at')
    op.drop_column('held_orders', 'payment_checkout_url')
    op.drop_column('held_orders', 'payment_qr_string')
    op.drop_column('held_orders', 'payment_external_id')
    op.drop_column('held_orders', 'payment_provider')
    op.drop_column('held_orders', 'payment_status')
