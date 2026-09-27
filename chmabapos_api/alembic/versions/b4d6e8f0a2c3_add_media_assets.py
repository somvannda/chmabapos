"""add_media_assets

Revision ID: b4d6e8f0a2c3
Revises: e7c1a2b3d4f5
Create Date: 2026-09-27 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4d6e8f0a2c3'
down_revision: Union[str, None] = 'e7c1a2b3d4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'media_assets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('content_type', sa.String(length=80), nullable=True),
        sa.Column('byte_size', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'sha256', name='uq_media_asset_company_sha'),
    )
    op.create_index(op.f('ix_media_assets_company_id'), 'media_assets', ['company_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_media_assets_company_id'), table_name='media_assets')
    op.drop_table('media_assets')
