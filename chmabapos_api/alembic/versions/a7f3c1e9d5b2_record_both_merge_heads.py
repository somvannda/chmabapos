"""record both reunions of the every-shop and backfill heads

``b6c8d0e2f4a6`` (Every shop guides) and ``b7e2f4a8c1d6`` (assistant-history
backfill) forked from ``a5b7c9d1e3f5``. Two fixes for that fork landed at almost
the same time — ``c3d9f1a7b5e2`` and ``c1d3e5f7a9b2`` — and each is a no-op
merge of the same pair, so they became two heads themselves.

This revision records that both are applied and leaves one head. It does
nothing on its own: both parents are already empty merges.

Revision ID: a7f3c1e9d5b2
Revises: c1d3e5f7a9b2, c3d9f1a7b5e2
Create Date: 2026-11-13
"""
from typing import Sequence, Union

revision: str = "a7f3c1e9d5b2"
down_revision: Union[str, Sequence[str], None] = ("c1d3e5f7a9b2", "c3d9f1a7b5e2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
