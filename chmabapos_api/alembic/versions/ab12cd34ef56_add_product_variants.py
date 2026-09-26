"""add_product_variants

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-26 00:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ab12cd34ef56'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_options',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'name', name='uq_product_option_product_name'),
    )
    op.create_index(op.f('ix_product_options_product_id'), 'product_options', ['product_id'], unique=False)

    op.create_table(
        'product_option_values',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('option_id', sa.UUID(), nullable=False),
        sa.Column('value', sa.String(length=80), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['option_id'], ['product_options.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('option_id', 'value', name='uq_product_option_value'),
    )
    op.create_index(op.f('ix_product_option_values_option_id'), 'product_option_values', ['option_id'], unique=False)

    op.create_table(
        'product_variants',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('sku', sa.String(length=80), nullable=False),
        sa.Column('barcode', sa.String(length=80), nullable=True),
        sa.Column('name', sa.String(length=180), nullable=False),
        sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('cost_price', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('attributes', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'sku', name='uq_variant_product_sku'),
    )
    op.create_index(op.f('ix_product_variants_product_id'), 'product_variants', ['product_id'], unique=False)
    op.create_index(op.f('ix_product_variants_barcode'), 'product_variants', ['barcode'], unique=False)

    op.create_table(
        'variant_inventory_balances',
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('variant_id', sa.UUID(), nullable=False),
        sa.Column('on_hand', sa.Integer(), nullable=False),
        sa.Column('reorder_point', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('store_id', 'variant_id'),
    )

    op.add_column('stock_movements', sa.Column('variant_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_stock_movements_variant_id'), 'stock_movements', ['variant_id'], unique=False)
    op.create_foreign_key('fk_stock_movements_variant_id_product_variants', 'stock_movements', 'product_variants', ['variant_id'], ['id'], ondelete='SET NULL')

    op.add_column('order_items', sa.Column('variant_id', sa.UUID(), nullable=True))
    op.add_column('order_items', sa.Column('variant_name', sa.String(length=180), nullable=True))
    op.create_foreign_key('fk_order_items_variant_id_product_variants', 'order_items', 'product_variants', ['variant_id'], ['id'], ondelete='RESTRICT')


def downgrade() -> None:
    op.drop_constraint('fk_order_items_variant_id_product_variants', 'order_items', type_='foreignkey')
    op.drop_column('order_items', 'variant_name')
    op.drop_column('order_items', 'variant_id')

    op.drop_constraint('fk_stock_movements_variant_id_product_variants', 'stock_movements', type_='foreignkey')
    op.drop_index(op.f('ix_stock_movements_variant_id'), table_name='stock_movements')
    op.drop_column('stock_movements', 'variant_id')

    op.drop_table('variant_inventory_balances')

    op.drop_index(op.f('ix_product_variants_barcode'), table_name='product_variants')
    op.drop_index(op.f('ix_product_variants_product_id'), table_name='product_variants')
    op.drop_table('product_variants')

    op.drop_index(op.f('ix_product_option_values_option_id'), table_name='product_option_values')
    op.drop_table('product_option_values')

    op.drop_index(op.f('ix_product_options_product_id'), table_name='product_options')
    op.drop_table('product_options')
