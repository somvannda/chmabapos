"""decimal_quantities

Revision ID: c9d8e7f6a5b4
Revises: b8c7d6e5f4a3
Create Date: 2026-09-26 01:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d8e7f6a5b4'
down_revision: Union[str, None] = 'b8c7d6e5f4a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('inventory_balances', 'on_hand', existing_type=sa.Integer(), type_=sa.Numeric(precision=12, scale=3), existing_nullable=False, postgresql_using='on_hand::numeric(12,3)')
    op.alter_column('variant_inventory_balances', 'on_hand', existing_type=sa.Integer(), type_=sa.Numeric(precision=12, scale=3), existing_nullable=False, postgresql_using='on_hand::numeric(12,3)')
    op.alter_column('stock_movements', 'quantity', existing_type=sa.Integer(), type_=sa.Numeric(precision=12, scale=3), existing_nullable=False, postgresql_using='quantity::numeric(12,3)')
    op.alter_column('order_items', 'quantity', existing_type=sa.Integer(), type_=sa.Numeric(precision=12, scale=3), existing_nullable=False, postgresql_using='quantity::numeric(12,3)')
    op.alter_column('product_batches', 'quantity_on_hand', existing_type=sa.Integer(), type_=sa.Numeric(precision=12, scale=3), existing_nullable=False, postgresql_using='quantity_on_hand::numeric(12,3)')


def downgrade() -> None:
    op.alter_column('product_batches', 'quantity_on_hand', existing_type=sa.Numeric(precision=12, scale=3), type_=sa.Integer(), existing_nullable=False, postgresql_using='quantity_on_hand::integer')
    op.alter_column('order_items', 'quantity', existing_type=sa.Numeric(precision=12, scale=3), type_=sa.Integer(), existing_nullable=False, postgresql_using='quantity::integer')
    op.alter_column('stock_movements', 'quantity', existing_type=sa.Numeric(precision=12, scale=3), type_=sa.Integer(), existing_nullable=False, postgresql_using='quantity::integer')
    op.alter_column('variant_inventory_balances', 'on_hand', existing_type=sa.Numeric(precision=12, scale=3), type_=sa.Integer(), existing_nullable=False, postgresql_using='on_hand::integer')
    op.alter_column('inventory_balances', 'on_hand', existing_type=sa.Numeric(precision=12, scale=3), type_=sa.Integer(), existing_nullable=False, postgresql_using='on_hand::integer')
