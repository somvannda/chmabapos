"""add_billing_cycle_to_subscriptions

Revision ID: a1b2c3d4e5f6
Revises: bfbd778dbbfd
Create Date: 2026-09-08 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'bfbd778dbbfd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('subscriptions', sa.Column('billing_cycle', sa.String(length=20), server_default='monthly', nullable=False))


def downgrade() -> None:
    op.drop_column('subscriptions', 'billing_cycle')
