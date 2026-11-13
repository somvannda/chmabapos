"""reunite the two equivalent post-backfill merge revisions

``c1d3e5f7a9b2`` (from #1054) and ``c3d9f1a7b5e2`` (from #1055) both merge the
same two parents, ``b6c8d0e2f4a6`` (every-shop guides) and
``b7e2f4a8c1d6`` (historical assistant backfill). They landed in parallel, so
Alembic sees two heads. This revision joins them without changing any data.

Revision ID: d5e1f3a9c7b4
Revises: c1d3e5f7a9b2, c3d9f1a7b5e2
Create Date: 2026-11-13
"""
from typing import Sequence, Union

revision: str = "d5e1f3a9c7b4"
down_revision: Union[str, Sequence[str], None] = ("c1d3e5f7a9b2", "c3d9f1a7b5e2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
