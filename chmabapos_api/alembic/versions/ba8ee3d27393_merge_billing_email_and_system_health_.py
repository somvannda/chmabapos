"""Finish the health/email-company head merge.

``371e8bc367eb`` already merged ``c9e2b4a8d1f6`` and ``2eb98b1092b9``. This
revision was created concurrently from the same two parents, so it must chain
after that merge rather than create a second head. It is intentionally empty.

Revision ID: ba8ee3d27393
Revises: 371e8bc367eb
Create Date: 2026-10-24
"""

from typing import Sequence, Union

revision: str = "ba8ee3d27393"
down_revision: Union[str, Sequence[str], None] = "371e8bc367eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
