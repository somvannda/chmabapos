"""add_dining_tables

Revision ID: d6e7f8a9b0c1
Revises: a0b1c2d3e4f5
Create Date: 2026-10-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, None] = 'a0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dining_areas',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'name', name='uq_dining_area_store_name'),
    )
    op.create_index(op.f('ix_dining_areas_store_id'), 'dining_areas', ['store_id'], unique=False)
    op.create_table(
        'dining_tables',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('area_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(length=40), nullable=False),
        sa.Column('seats', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='available'),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['area_id'], ['dining_areas.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'name', name='uq_dining_table_store_name'),
    )
    op.create_index(op.f('ix_dining_tables_store_id'), 'dining_tables', ['store_id'], unique=False)
    op.create_index('ix_dining_table_area', 'dining_tables', ['area_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_dining_table_area', table_name='dining_tables')
    op.drop_index(op.f('ix_dining_tables_store_id'), table_name='dining_tables')
    op.drop_table('dining_tables')
    op.drop_index(op.f('ix_dining_areas_store_id'), table_name='dining_areas')
    op.drop_table('dining_areas')
