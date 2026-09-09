"""add users.google_sub for Google Sign-In

Revision ID: e6f4a8c2d1b9
Revises: b7e1c3a9d5f6
Create Date: 2026-09-09 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6f4a8c2d1b9'
down_revision: Union[str, None] = 'b7e1c3a9d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('google_sub', sa.String(length=255), nullable=True))
    op.create_index('ix_users_google_sub', 'users', ['google_sub'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_google_sub', table_name='users')
    op.drop_column('users', 'google_sub')
