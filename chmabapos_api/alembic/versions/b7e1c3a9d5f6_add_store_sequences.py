"""add store sequences + per-store unique document numbers

Revision ID: b7e1c3a9d5f6
Revises: 7a3f9d1c4e0b
Create Date: 2026-09-08 22:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e1c3a9d5f6'
down_revision: Union[str, None] = '7a3f9d1c4e0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'store_sequences',
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('scope', sa.String(length=20), nullable=False),
        sa.Column('next_value', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('store_id', 'scope'),
    )
    # Document numbers are now sequential per store rather than globally unique.
    # Existing data is already unique, so scoping the uniqueness to (store, number)
    # is a safe narrowing that lets each branch run its own run of numbers.
    op.drop_constraint('orders_order_number_key', 'orders', type_='unique')
    op.create_unique_constraint('uq_order_store_number', 'orders', ['store_id', 'order_number'])
    op.drop_constraint('purchase_orders_po_number_key', 'purchase_orders', type_='unique')
    op.create_unique_constraint('uq_purchase_order_store_number', 'purchase_orders', ['store_id', 'po_number'])


def downgrade() -> None:
    op.drop_constraint('uq_purchase_order_store_number', 'purchase_orders', type_='unique')
    op.create_unique_constraint('purchase_orders_po_number_key', 'purchase_orders', ['po_number'])
    op.drop_constraint('uq_order_store_number', 'orders', type_='unique')
    op.create_unique_constraint('orders_order_number_key', 'orders', ['order_number'])
    op.drop_table('store_sequences')
