"""add_platform_activities

Revision ID: c9f1a2b3d4e5
Revises: b7c8d9e0f1a2
Create Date: 2026-09-25 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9f1a2b3d4e5'
down_revision: Union[str, None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'platform_activities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('company_id', sa.UUID(), nullable=True),
        sa.Column('store_id', sa.UUID(), nullable=True),
        sa.Column('event_type', sa.String(length=60), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_platform_activity_created', 'platform_activities', ['created_at'], unique=False)
    op.create_index('ix_platform_activity_type_created', 'platform_activities', ['event_type', 'created_at'], unique=False)
    op.create_index('ix_platform_activity_user_created', 'platform_activities', ['user_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_platform_activities_event_type'), 'platform_activities', ['event_type'], unique=False)
    op.create_index(op.f('ix_platform_activities_user_id'), 'platform_activities', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_platform_activities_user_id'), table_name='platform_activities')
    op.drop_index(op.f('ix_platform_activities_event_type'), table_name='platform_activities')
    op.drop_index('ix_platform_activity_user_created', table_name='platform_activities')
    op.drop_index('ix_platform_activity_type_created', table_name='platform_activities')
    op.drop_index('ix_platform_activity_created', table_name='platform_activities')
    op.drop_table('platform_activities')
