"""add_product_core_fields

Revision ID: b2c3d4e5f6a7
Revises: c9f1a2b3d4e5
Create Date: 2026-09-26 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'c9f1a2b3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('vertical', sa.String(length=20), nullable=False, server_default='general'))
    op.add_column('products', sa.Column('barcode', sa.String(length=80), nullable=True))
    op.add_column('products', sa.Column('brand', sa.String(length=120), nullable=True))
    op.add_column('products', sa.Column('unit', sa.String(length=20), nullable=False, server_default='each'))
    op.add_column('products', sa.Column('track_inventory', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('products', sa.Column('track_serials', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('products', sa.Column('attributes', sa.JSON(), nullable=True))
    op.create_index('ix_products_barcode', 'products', ['barcode'])


def downgrade() -> None:
    op.drop_index('ix_products_barcode', table_name='products')
    op.drop_column('products', 'attributes')
    op.drop_column('products', 'track_serials')
    op.drop_column('products', 'track_inventory')
    op.drop_column('products', 'unit')
    op.drop_column('products', 'brand')
    op.drop_column('products', 'barcode')
    op.drop_column('companies', 'vertical')
