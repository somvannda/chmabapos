"""add_product_serials

Revision ID: d5e6f7a8b9c0
Revises: ab12cd34ef56
Create Date: 2026-09-26 00:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'ab12cd34ef56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_serials',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('variant_id', sa.UUID(), nullable=True),
        sa.Column('store_id', sa.UUID(), nullable=True),
        sa.Column('serial_number', sa.String(length=120), nullable=False),
        sa.Column('imei', sa.String(length=40), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('cost_price', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('warranty_months', sa.Integer(), nullable=True),
        sa.Column('warranty_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('order_item_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_item_id'], ['order_items.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'serial_number', name='uq_serial_company_number'),
    )
    op.create_index(op.f('ix_product_serials_company_id'), 'product_serials', ['company_id'], unique=False)
    op.create_index(op.f('ix_product_serials_variant_id'), 'product_serials', ['variant_id'], unique=False)
    op.create_index(op.f('ix_product_serials_store_id'), 'product_serials', ['store_id'], unique=False)
    op.create_index('ix_product_serial_product', 'product_serials', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_product_serial_product', table_name='product_serials')
    op.drop_index(op.f('ix_product_serials_store_id'), table_name='product_serials')
    op.drop_index(op.f('ix_product_serials_variant_id'), table_name='product_serials')
    op.drop_index(op.f('ix_product_serials_company_id'), table_name='product_serials')
    op.drop_table('product_serials')
