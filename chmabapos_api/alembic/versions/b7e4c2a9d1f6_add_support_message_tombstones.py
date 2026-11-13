"""Add soft-delete tombstones to support chat messages.

Deleting a support message keeps the row so both sides can render a tombstone
and the realtime cursor stays stable. ``deleted_by`` records who removed it;
the body and attachment are cleared so the content is gone.

Revision ID: b7e4c2a9d1f6
Revises: f1b3d5e7a9c2
Create Date: 2026-11-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7e4c2a9d1f6"
down_revision: Union[str, None] = "f1b3d5e7a9c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("support_chat_messages", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("support_chat_messages", sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_support_chat_messages_deleted_by",
        "support_chat_messages",
        "users",
        ["deleted_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_support_chat_message_conversation_deleted",
        "support_chat_messages",
        ["conversation_id", "deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_support_chat_message_conversation_deleted", table_name="support_chat_messages")
    op.drop_constraint("fk_support_chat_messages_deleted_by", "support_chat_messages", type_="foreignkey")
    op.drop_column("support_chat_messages", "deleted_by")
    op.drop_column("support_chat_messages", "deleted_at")
