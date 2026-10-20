"""Merge the delivery-help and order-rate heads.

Two migrations landed from concurrent branches (``d6e3a1b8c4f2`` from the help
article and ``e7d9c1b3a5f2`` from the order base rate), both branching from
``f9a1c3e5b7d2``, leaving ``alembic heads`` with two revisions. Join them here so
the tree has a single head again; the next migration (checkout coverage) chains
onto this merge.

Revision ID: b8e2f4a6c0d3
Revises: d6e3a1b8c4f2, e7d9c1b3a5f2
Create Date: 2026-10-20
"""

from typing import Sequence, Union

revision: str = "b8e2f4a6c0d3"
down_revision: Union[str, Sequence[str], None] = ("d6e3a1b8c4f2", "e7d9c1b3a5f2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
