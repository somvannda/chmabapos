"""add_held_order_table

Revision ID: f1a2b3c4d5e6
Revises: a4b5c6d7e8f9
Create Date: 2026-10-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Open tickets: a held order may now serve a dining table. The table keeps
    # its own denormalised status; this link is what the floor uses to free it.
    op.add_column('held_orders', sa.Column('table_id', sa.UUID(), nullable=True))
    op.add_column('held_orders', sa.Column('status', sa.String(length=20), nullable=False, server_default='open'))
    op.create_foreign_key('fk_held_orders_table_id', 'held_orders', 'dining_tables', ['table_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_held_orders_table_id', 'held_orders', type_='foreignkey')
    op.drop_column('held_orders', 'status')
    op.drop_column('held_orders', 'table_id')
