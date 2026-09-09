"""add_user_preferences

Revision ID: 7a3f9d1c4e0b
Revises: 9e4c7a1d5f8b
Create Date: 2026-09-08 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a3f9d1c4e0b'
down_revision: Union[str, None] = '9e4c7a1d5f8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('preferences', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'preferences')
