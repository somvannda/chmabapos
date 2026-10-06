"""add_order_redeemed_points

Revision ID: 9f8e7d6c5b4a
Revises: e5a9c1d2b3f4
Create Date: 2026-10-06 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9f8e7d6c5b4a'
down_revision: Union[str, None] = 'e5a9c1d2b3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('redeemed_points', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('orders', 'redeemed_points')
