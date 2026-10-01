"""add_order_table

Revision ID: d7e8f9a0b1c2
Revises: cc11dd22ee33
Create Date: 2026-10-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, None] = 'cc11dd22ee33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Snapshot the table a dine-in sale was served at. Nullable so existing
    # orders are unaffected; SET NULL so deleting a table keeps the sale.
    op.add_column('orders', sa.Column('table_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_orders_table_id', 'orders', 'dining_tables', ['table_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_orders_table_id', 'orders', type_='foreignkey')
    op.drop_column('orders', 'table_id')
