"""Merge the billing-email and system-health migration heads.

Revision ID: ba8ee3d27393
Revises: 2eb98b1092b9, c9e2b4a8d1f6
Create Date: 2026-10-24
"""

from typing import Sequence, Union

revision: str = "ba8ee3d27393"
down_revision: Union[str, Sequence[str], None] = ("2eb98b1092b9", "c9e2b4a8d1f6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
