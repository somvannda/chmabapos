"""join the two identical post-#1054 merge revisions

``a7f3c1e9d5b2`` (from #1056) and ``d5e1f3a9c7b4`` (from #1058) both merge
``c1d3e5f7a9b2`` and ``c3d9f1a7b5e2``. They landed in parallel, so Alembic sees
two heads. This no-op revision joins them and leaves exactly one head.

Revision ID: e7a1c3f5b9d2
Revises: a7f3c1e9d5b2, d5e1f3a9c7b4
Create Date: 2026-11-13
"""
from typing import Sequence, Union

revision: str = "e7a1c3f5b9d2"
down_revision: Union[str, Sequence[str], None] = ("a7f3c1e9d5b2", "d5e1f3a9c7b4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
