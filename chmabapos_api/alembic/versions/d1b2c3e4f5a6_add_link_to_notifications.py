"""Add an in-workspace link to notifications, so a reminder can be acted on.

A billing renewal reminder could only be read; the owner still had to find the
Billing page themselves. A relative destination (path + query, never an absolute
URL) lets the bell row open Billing with the renewal pre-selected, and the client
resolves it against the signed-in account.

Revision ID: d1b2c3e4f5a6
Revises: c5d9e2f8a1b4
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1b2c3e4f5a6"
down_revision: Union[str, None] = "c5d9e2f8a1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("link", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("notifications", "link")
