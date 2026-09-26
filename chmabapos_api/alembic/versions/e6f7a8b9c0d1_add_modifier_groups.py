"""add_modifier_groups

Revision ID: e6f7a8b9c0d1
Revises: ab12cd34ef56
Create Date: 2026-09-26 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'modifier_groups',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('min_select', sa.Integer(), nullable=False),
        sa.Column('max_select', sa.Integer(), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_modifier_groups_company_id'), 'modifier_groups', ['company_id'], unique=False)

    op.create_table(
        'modifiers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('price_delta', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('ingredient_product_id', sa.UUID(), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['modifier_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ingredient_product_id'], ['products.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_modifiers_group_id'), 'modifiers', ['group_id'], unique=False)
    op.add_column('products', sa.Column('modifier_group_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_products_modifier_group_id', 'products', 'modifier_groups', ['modifier_group_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_products_modifier_group_id', 'products', type_='foreignkey')
    op.drop_column('products', 'modifier_group_id')
    op.drop_index(op.f('ix_modifiers_group_id'), table_name='modifiers')
    op.drop_table('modifiers')
    op.drop_index(op.f('ix_modifier_groups_company_id'), table_name='modifier_groups')
    op.drop_table('modifier_groups')
