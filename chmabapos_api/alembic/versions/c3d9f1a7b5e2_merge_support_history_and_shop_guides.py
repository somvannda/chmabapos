"""reunite the historical-chat backfill with the every-shop guide migration

``b7e2f4a8c1d6`` (historical assistant chat backfill) and
``b6c8d0e2f4a6`` (Every shop guide path) were both based on
``a5b7c9d1e3f5``. They touch different content and can be applied in either
order, so this merge revision only records that both must run before the graph
continues.

Revision ID: c3d9f1a7b5e2
Revises: b6c8d0e2f4a6, b7e2f4a8c1d6
Create Date: 2026-11-13
"""
from typing import Sequence, Union

revision: str = "c3d9f1a7b5e2"
down_revision: Union[str, Sequence[str], None] = ("b6c8d0e2f4a6", "b7e2f4a8c1d6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
