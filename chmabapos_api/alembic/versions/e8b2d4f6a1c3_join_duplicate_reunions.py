"""join the two duplicate reunions of the same pair

``a7f3c1e9d5b2`` (from #1056) and ``d5e1f3a9c7b4`` (from #1058) both reunite
``c1d3e5f7a9b2`` and ``c3d9f1a7b5e2`` — themselves two no-op merges of the same
fork. Two equivalent reunions landed in parallel, so they are heads themselves.

This revision joins them and changes nothing else. The underlying data is
already correct whichever order the two reunions ran in.

Revision ID: e8b2d4f6a1c3
Revises: a7f3c1e9d5b2, d5e1f3a9c7b4
Create Date: 2026-11-13
"""
from typing import Sequence, Union

revision: str = "e8b2d4f6a1c3"
down_revision: Union[str, Sequence[str], None] = ("a7f3c1e9d5b2", "d5e1f3a9c7b4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
