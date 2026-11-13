"""reunite the support-chat and guide-copy migration heads

``b9d0f2a4c6e8`` (the refreshed guide copy) and ``d1f3a7c9e2b4`` (live support
chat) were created on parallel branches from the same parent. Neither changes
the other's tables, so this merge revision only records that both must be
applied before the graph continues.

Revision ID: e5a1b3c7d9f2
Revises: b9d0f2a4c6e8, d1f3a7c9e2b4
Create Date: 2026-11-13
"""
from typing import Sequence, Union

revision: str = "e5a1b3c7d9f2"
down_revision: Union[str, Sequence[str], None] = ("b9d0f2a4c6e8", "d1f3a7c9e2b4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
