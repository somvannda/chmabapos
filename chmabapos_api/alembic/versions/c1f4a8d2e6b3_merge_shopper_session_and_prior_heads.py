"""Merge the shopper-session and prior merge-heads revisions.

A session's shopper-session migration forked from a parent that already had the
product-card merge, leaving two heads, and `alembic upgrade head` refuses to run
with more than one -- which keeps the API container down. This reunites them.

Revision ID: c1f4a8d2e6b3
Revises: a3d5f7b9c1e2, b4e8f2a6c3d1
Create Date: 2026-10-19
"""

from typing import Sequence, Union

revision: str = "c1f4a8d2e6b3"
down_revision: Union[str, Sequence[str], None] = ("a3d5f7b9c1e2", "b4e8f2a6c3d1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
