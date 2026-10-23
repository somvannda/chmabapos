"""Per-campaign send windows.

A scheduled campaign can carry its own quiet hours instead of inheriting the
drip window. Null keeps the inherited behaviour.

Revision ID: c9e2f4a6b8d1
Revises: b8d3f1a6c9e2
Create Date: 2026-10-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9e2f4a6b8d1"
down_revision: Union[str, None] = "b8d3f1a6c9e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mailing_campaigns", sa.Column("send_window", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("mailing_campaigns", "send_window")
