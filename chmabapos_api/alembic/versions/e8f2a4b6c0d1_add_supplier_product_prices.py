"""add_supplier_product_prices

Adds ``supplier_product_prices``: the cost one supplier charges for a product
or for a specific variant. This lets the same specification bought from several
suppliers at different prices be compared without duplicating the variant.

Revision ID: e8f2a4b6c0d1
Revises: c4a8f2b6d1e9
Create Date: 2026-10-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e8f2a4b6c0d1'
down_revision: Union[str, None] = 'c4a8f2b6d1e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'supplier_product_prices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('supplier_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('variant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('unit_cost', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency_code', sa.String(length=3), nullable=True),
        sa.Column('supplier_sku', sa.String(length=80), nullable=True),
        sa.Column('lead_time_days', sa.Integer(), nullable=True),
        sa.Column('min_order_qty', sa.Integer(), nullable=True),
        sa.Column('is_preferred', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['currency_code'], ['currencies.code']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_supplier_price_company_product', 'supplier_product_prices', ['company_id', 'product_id'])
    op.create_index('ix_supplier_product_prices_company_id', 'supplier_product_prices', ['company_id'])
    op.create_index('ix_supplier_product_prices_supplier_id', 'supplier_product_prices', ['supplier_id'])
    op.create_index('ix_supplier_product_prices_product_id', 'supplier_product_prices', ['product_id'])
    op.create_index('ix_supplier_product_prices_variant_id', 'supplier_product_prices', ['variant_id'])
    # Partial unique indexes give exactly one row per supplier per target even
    # though PostgreSQL treats NULLs as distinct.
    op.create_index(
        'uq_supplier_price_product', 'supplier_product_prices', ['supplier_id', 'product_id'],
        unique=True, postgresql_where=sa.text('variant_id IS NULL'),
    )
    op.create_index(
        'uq_supplier_price_variant', 'supplier_product_prices', ['supplier_id', 'variant_id'],
        unique=True, postgresql_where=sa.text('variant_id IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_supplier_price_variant', table_name='supplier_product_prices')
    op.drop_index('uq_supplier_price_product', table_name='supplier_product_prices')
    op.drop_index('ix_supplier_product_prices_variant_id', table_name='supplier_product_prices')
    op.drop_index('ix_supplier_product_prices_product_id', table_name='supplier_product_prices')
    op.drop_index('ix_supplier_product_prices_supplier_id', table_name='supplier_product_prices')
    op.drop_index('ix_supplier_product_prices_company_id', table_name='supplier_product_prices')
    op.drop_index('ix_supplier_price_company_product', table_name='supplier_product_prices')
    op.drop_table('supplier_product_prices')
