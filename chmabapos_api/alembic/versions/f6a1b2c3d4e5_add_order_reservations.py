"""add_order_reservations

Revision ID: f6a1b2c3d4e5
Revises: a5b6c7d8e9f0
Create Date: 2026-10-04 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a1b2c3d4e5'
down_revision: Union[str, None] = 'a5b6c7d8e9f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reservation / deposit support. Existing rows are plain paid sales, so the
    # new columns default to "no reservation" and never change their meaning.
    op.add_column('orders', sa.Column('pickup_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('pickup_note', sa.Text(), nullable=True))
    op.add_column('orders', sa.Column('reservation_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('stock_held', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('orders', sa.Column('deposit', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'))
    op.create_index('ix_order_reservation_expiry', 'orders', ['reservation_expires_at'])


def downgrade() -> None:
    op.drop_index('ix_order_reservation_expiry', table_name='orders')
    op.drop_column('orders', 'deposit')
    op.drop_column('orders', 'stock_held')
    op.drop_column('orders', 'reservation_expires_at')
    op.drop_column('orders', 'pickup_note')
    op.drop_column('orders', 'pickup_at')
