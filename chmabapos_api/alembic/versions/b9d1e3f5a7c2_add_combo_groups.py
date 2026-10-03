"""add_combo_groups

Combos with choice (docs/combos-choice-plan.md): a combo may offer choose-from-a-set
groups alongside its fixed items.

Revision ID: b9d1e3f5a7c2
Revises: a7c3e9f1b2d4
Create Date: 2026-10-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b9d1e3f5a7c2'
down_revision: Union[str, None] = 'a7c3e9f1b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'combo_groups',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('combo_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('min_select', sa.Integer(), nullable=False),
        sa.Column('max_select', sa.Integer(), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['combo_id'], ['combos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_combo_groups_combo_id'), 'combo_groups', ['combo_id'], unique=False)

    op.create_table(
        'combo_group_options',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.UUID(), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('variant_id', sa.UUID(), nullable=True),
        sa.Column('price_delta', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['combo_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_combo_group_options_group_id'), 'combo_group_options', ['group_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_combo_group_options_group_id'), table_name='combo_group_options')
    op.drop_table('combo_group_options')
    op.drop_index(op.f('ix_combo_groups_combo_id'), table_name='combo_groups')
    op.drop_table('combo_groups')
