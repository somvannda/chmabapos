"""add_order_item_seat_course

Dine-in seat/course routing (docs/seat-course-plan.md): snapshot which seat
ordered a line and which course it belongs to onto the settled order line.

Revision ID: b4a3c2d1e0f9
Revises: b9d1e3f5a7c2
Create Date: 2026-10-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4a3c2d1e0f9'
down_revision: Union[str, None] = 'b9d1e3f5a7c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('order_items', sa.Column('seat', sa.Integer(), nullable=True))
    op.add_column('order_items', sa.Column('course', sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column('order_items', 'course')
    op.drop_column('order_items', 'seat')
