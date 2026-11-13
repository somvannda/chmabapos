"""join the identical reunion that landed twice

``e7a1c3f5b9d2`` (from #1059) and ``e8b2d4f6a1c3`` (from #1053) both reunite
``a7f3c1e9d5b2`` and ``d5e1f3a9c7b4``, which are themselves identical reunions
of ``c1d3e5f7a9b2`` and ``c3d9f1a7b5e2``. Each fix was correct on its own and
landed within minutes of the other, so each became a head.

This revision joins the pair and changes no data: every underlying migration
has already run, in one order or the other.

The durable fix is process, not another revision: a branch that merges main
while main has two heads should not add its own reunion. Land one reunion,
then rebase the others onto it.

Revision ID: f1b3d5e7a9c2
Revises: e7a1c3f5b9d2, e8b2d4f6a1c3
Create Date: 2026-11-13
"""
from typing import Sequence, Union

revision: str = "f1b3d5e7a9c2"
down_revision: Union[str, Sequence[str], None] = ("e7a1c3f5b9d2", "e8b2d4f6a1c3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
