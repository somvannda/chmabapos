"""add_online_ordering

Online ordering / QR-at-table (docs/online-ordering-plan.md): a public,
tokenised ordering surface that feeds the existing held-ticket engine.

Revision ID: a5b6c7d8e9f0
Revises: f2b3c4d5e6a7
Create Date: 2026-10-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a5b6c7d8e9f0'
down_revision: Union[str, None] = 'f2b3c4d5e6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stores', sa.Column('public_order_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('stores', sa.Column('public_order_token', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_store_public_order_token', 'stores', ['public_order_token'])

    op.add_column('dining_tables', sa.Column('qr_token', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_dining_table_qr_token', 'dining_tables', ['qr_token'])

    # Public orders have no staff author, so created_by must allow NULL.
    op.alter_column('held_orders', 'created_by', existing_type=sa.UUID(), nullable=True)
    op.add_column('held_orders', sa.Column('source', sa.String(length=20), nullable=False, server_default='pos'))
    op.add_column('held_orders', sa.Column('customer_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('held_orders', 'customer_note')
    op.drop_column('held_orders', 'source')
    op.alter_column('held_orders', 'created_by', existing_type=sa.UUID(), nullable=False)
    op.drop_constraint('uq_dining_table_qr_token', 'dining_tables', type_='unique')
    op.drop_column('dining_tables', 'qr_token')
    op.drop_constraint('uq_store_public_order_token', 'stores', type_='unique')
    op.drop_column('stores', 'public_order_token')
    op.drop_column('stores', 'public_order_enabled')
