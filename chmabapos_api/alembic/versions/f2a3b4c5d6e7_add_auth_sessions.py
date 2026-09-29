"""add_auth_sessions

Server-side sign-in sessions that back rotating refresh tokens. The access
token only references a session by id, so logout and revocation take effect
immediately instead of waiting for the bearer token to expire.

Revision ID: f2a3b4c5d6e7
Revises: c1f4a7b2d9e3
Create Date: 2026-09-29 16:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'c1f4a7b2d9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'auth_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('refresh_token_hash', sa.String(length=64), nullable=False),
        sa.Column('previous_token_hash', sa.String(length=64), nullable=True),
        sa.Column('remember', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('refresh_token_hash'),
    )
    op.create_index('ix_auth_sessions_user', 'auth_sessions', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_auth_sessions_user', table_name='auth_sessions')
    op.drop_table('auth_sessions')
