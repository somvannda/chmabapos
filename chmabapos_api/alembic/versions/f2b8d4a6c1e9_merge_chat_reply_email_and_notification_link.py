"""Merge the chat reply-email and notification-link migrations.

Two branches forked from c5d9e2f8a1b4: the chat "customer notified" marker and
the notification link column. Nothing depends on their order, so a merge revision
reunites them into one head and keeps ``alembic upgrade head`` valid.

Revision ID: f2b8d4a6c1e9
Revises: d1b2c3e4f5a6, d7a3f8c1e5b9
Create Date: 2026-10-19
"""

from typing import Sequence, Union

revision: str = "f2b8d4a6c1e9"
down_revision: Union[str, Sequence[str], None] = ("d1b2c3e4f5a6", "d7a3f8c1e5b9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
