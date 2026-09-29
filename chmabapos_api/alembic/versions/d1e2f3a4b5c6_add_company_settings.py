"""add_company_settings

Revision ID: d1e2f3a4b5c6
Revises: c5e7f9a1b3d2
Create Date: 2026-09-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c5e7f9a1b3d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Company-wide settings bag (approval policy and future controls).
    op.add_column('companies', sa.Column('settings', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('companies', 'settings')
