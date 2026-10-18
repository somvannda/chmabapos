"""Reusable chat replies for the store inbox.

Opening hours, delivery area, returns - answers a counter gives all day. Storing
them per store lets the inbox drop one in with a tap instead of retyping it,
which is what makes a fast reply realistic at a busy counter.

Revision ID: e2b6c4a8f1d3
Revises: c3f8a1d6e4b7
Create Date: 2026-10-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e2b6c4a8f1d3"
down_revision: Union[str, None] = "c3f8a1d6e4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "store_chat_canned_replies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(length=60), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_store_chat_canned_replies_store_id", "store_chat_canned_replies", ["store_id"])
    op.create_index("ix_store_chat_canned_store_position", "store_chat_canned_replies", ["store_id", "position"])


def downgrade() -> None:
    op.drop_index("ix_store_chat_canned_store_position", table_name="store_chat_canned_replies")
    op.drop_index("ix_store_chat_canned_replies_store_id", table_name="store_chat_canned_replies")
    op.drop_table("store_chat_canned_replies")
