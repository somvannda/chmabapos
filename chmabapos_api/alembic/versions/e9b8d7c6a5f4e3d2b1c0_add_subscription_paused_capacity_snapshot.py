"""add_subscription_paused_capacity_snapshot

Records which stores/members the expiry job force-paused when a workspace fell
back to the Free plan. The snapshot lives on the Free fallback subscription so
a later paid payment can auto-restore exactly those items (up to the new
plan's capacity) instead of resurrecting intentionally-deactivated ones.

Revision ID: e9b8d7c6a5f4e3d2b1c0
Revises: d7a9c2f5b8e3a1f0d6c4
Create Date: 2026-09-09 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e9b8d7c6a5f4e3d2b1c0'
down_revision: Union[str, None] = 'd7a9c2f5b8e3a1f0d6c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('subscriptions', sa.Column('paused_store_ids', sa.JSON(), nullable=True))
    op.add_column('subscriptions', sa.Column('paused_member_ids', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('subscriptions', 'paused_member_ids')
    op.drop_column('subscriptions', 'paused_store_ids')
