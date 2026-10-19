"""Claim a chat thread and keep internal notes on it.

Two staff can already answer the same thread, and the second one has no way to
know the first is on it. ``assigned_user_id`` is who has taken it; ``internal_notes``
is a scratchpad the customer never sees. Both are store-side only.

Revision ID: c5d9e2f8a1b4
Revises: b3e7f1a9c5d2
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5d9e2f8a1b4"
down_revision: Union[str, None] = "b3e7f1a9c5d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "store_chat_conversations",
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("store_chat_conversations", sa.Column("internal_notes", sa.String(length=2000), nullable=True))


def downgrade() -> None:
    op.drop_column("store_chat_conversations", "internal_notes")
    op.drop_column("store_chat_conversations", "assigned_user_id")
