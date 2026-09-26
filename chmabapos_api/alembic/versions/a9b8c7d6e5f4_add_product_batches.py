"""add_product_batches

Revision ID: a9b8c7d6e5f4
Revises: d5e6f7a8b9c0
Create Date: 2026-09-26 00:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_batches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('variant_id', sa.UUID(), nullable=True),
        sa.Column('store_id', sa.UUID(), nullable=True),
        sa.Column('batch_code', sa.String(length=80), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('quantity_on_hand', sa.Integer(), nullable=False),
        sa.Column('cost_price', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_product_batches_company_id'), 'product_batches', ['company_id'], unique=False)
    op.create_index(op.f('ix_product_batches_store_id'), 'product_batches', ['store_id'], unique=False)
    op.create_index('ix_product_batch_product_expiry', 'product_batches', ['product_id', 'expiry_date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_product_batch_product_expiry', table_name='product_batches')
    op.drop_index(op.f('ix_product_batches_store_id'), table_name='product_batches')
    op.drop_index(op.f('ix_product_batches_company_id'), table_name='product_batches')
    op.drop_table('product_batches')
