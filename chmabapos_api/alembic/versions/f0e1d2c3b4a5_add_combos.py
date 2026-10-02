"""add_combos

Combos / meal deals: a named bundle of products sold for a single price. A combo
is logical, not stocked -- selling one deducts each component's inventory (like a
recipe). See docs/combos-plan.md.

Revision ID: f0e1d2c3b4a5
Revises: d4a7b1e9c2f6
Create Date: 2026-10-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f0e1d2c3b4a5'
down_revision: Union[str, None] = 'd4a7b1e9c2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'combos',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=180), nullable=False),
        sa.Column('sku', sa.String(length=80), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('image', sa.String(length=500), nullable=True),
        sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'sku', name='uq_combo_company_sku'),
    )
    op.create_index(op.f('ix_combos_company_id'), 'combos', ['company_id'], unique=False)

    op.create_table(
        'combo_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('combo_id', sa.UUID(), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('variant_id', sa.UUID(), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['combo_id'], ['combos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_combo_items_combo_id'), 'combo_items', ['combo_id'], unique=False)

    op.add_column('order_items', sa.Column('combo_id', sa.UUID(), nullable=True))
    op.add_column('order_items', sa.Column('combo_name', sa.String(length=180), nullable=True))
    op.add_column('order_items', sa.Column('combo_components', sa.JSON(), nullable=True))
    op.create_foreign_key('fk_order_items_combo_id', 'order_items', 'combos', ['combo_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_order_items_combo_id'), 'order_items', ['combo_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_order_items_combo_id'), table_name='order_items')
    op.drop_constraint('fk_order_items_combo_id', 'order_items', type_='foreignkey')
    op.drop_column('order_items', 'combo_components')
    op.drop_column('order_items', 'combo_name')
    op.drop_column('order_items', 'combo_id')

    op.drop_index(op.f('ix_combo_items_combo_id'), table_name='combo_items')
    op.drop_table('combo_items')
    op.drop_index(op.f('ix_combos_company_id'), table_name='combos')
    op.drop_table('combos')
