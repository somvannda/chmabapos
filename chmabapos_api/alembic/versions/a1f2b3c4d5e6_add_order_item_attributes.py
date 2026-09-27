"""add_order_item_attributes

Revision ID: a1f2b3c4d5e6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-27 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1f2b3c4d5e6'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('order_items', sa.Column('attributes', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('order_items', 'attributes')
