"""add_order_client_id

Revision ID: a1a1a1a1a1a1
Revises: 9f8e7d6c5b4a
Create Date: 2026-10-06 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1a1a1a1a1a1'
down_revision: Union[str, None] = '9f8e7d6c5b4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('client_order_id', sa.String(length=64), nullable=True))
    op.create_index('ix_orders_store_client_order', 'orders', ['store_id', 'client_order_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_orders_store_client_order', table_name='orders')
    op.drop_column('orders', 'client_order_id')
