"""Merge the shopper-session and chat-product-link branches.

Two migrations landed independently, both chained to ``f2b8d4a6c1e9``: the
customer-to-shopper link and the chat-product link. That left ``main`` with two
heads, so ``alembic upgrade head`` refused to run - which would have blocked the
next deploy, not just this branch. A merge revision with no operations reconciles
them and restores the single-head invariant.

Revision ID: b4e6f8a0c2d3
Revises: e2c3d4f5a6b7, a3c9e1f5b7d2
Create Date: 2026-10-19
"""

from typing import Sequence, Union

revision: str = "b4e6f8a0c2d3"
down_revision: Union[str, Sequence[str], None] = ("e2c3d4f5a6b7", "a3c9e1f5b7d2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
