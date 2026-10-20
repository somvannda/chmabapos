"""Merge the two migrations that landed on the same parent.

Both were chained to f9a1c3e5b7d2 and merged separately, leaving main with two
heads - which the CI head check now names instead of failing inside `upgrade head`.
No operations: the two branches are independent.

Revision ID: f2a4c6e8b0d1
Revises: d6e3a1b8c4f2, e7d9c1b3a5f2
Create Date: 2026-10-20
"""

from typing import Sequence, Union

revision: str = "f2a4c6e8b0d1"
down_revision: Union[str, Sequence[str], None] = ("d6e3a1b8c4f2", "e7d9c1b3a5f2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
