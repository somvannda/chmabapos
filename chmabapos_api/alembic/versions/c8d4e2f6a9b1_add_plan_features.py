"""add_plan_features

Revision ID: c8d4e2f6a9b1
Revises: a1b2c3d4e5f6
Create Date: 2026-09-08 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8d4e2f6a9b1'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('plans', sa.Column('description', sa.String(length=255), nullable=True))
    op.add_column('plans', sa.Column('capabilities', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('plans', sa.Column('marketing_features', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    op.drop_column('plans', 'marketing_features')
    op.drop_column('plans', 'capabilities')
    op.drop_column('plans', 'description')
