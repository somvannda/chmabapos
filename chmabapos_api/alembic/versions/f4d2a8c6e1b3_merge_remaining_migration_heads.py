"""Merge the two equivalent order-rate/delivery-help merge revisions.

PR #938 and PR #939 both merged the same pair of branches
(``d6e3a1b8c4f2`` and ``e7d9c1b3a5f2``) at nearly the same time, producing two
merge revisions (``b8e2f4a6c0d3`` and ``a3f5c7e9b1d2``) and two heads. The
checkout-coverage branch (``f2a4c6e8b0d1``) continues from one of them.

This revision reunites ``a3f5c7e9b1d2`` with ``f2a4c6e8b0d1`` without removing
either merge from history, so databases already stamped at either revision keep
working and ``alembic upgrade head`` resolves to one head again.

Revision ID: f4d2a8c6e1b3
Revises: a3f5c7e9b1d2, f2a4c6e8b0d1
Create Date: 2026-10-20
"""

from typing import Sequence, Union

revision: str = "f4d2a8c6e1b3"
down_revision: Union[str, Sequence[str], None] = ("a3f5c7e9b1d2", "f2a4c6e8b0d1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
