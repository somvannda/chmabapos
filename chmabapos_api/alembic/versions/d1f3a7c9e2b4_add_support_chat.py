"""Live support chat between a merchant workspace and the Chmaba team.

Adds the two tables behind the merchant <-> human support channel. It is shaped
like ``store_chat_*`` on purpose: a conversation carries unread counters and a
last-message preview, and each message carries a database identity ``seq`` used
as the realtime cursor. The assistant (``support_conversations``) is untouched;
its answers are written into ``support_chat_messages`` so a hand-off keeps the
whole conversation in one thread.

Revision ID: d1f3a7c9e2b4
Revises: c7f2e9a4d1b8
Create Date: 2026-11-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d1f3a7c9e2b4"
down_revision: Union[str, None] = "c7f2e9a4d1b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "support_chat_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference", sa.String(length=20), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ai"),
        sa.Column("priority", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("assigned_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_preview", sa.String(length=200), nullable=True),
        sa.Column("last_message_author", sa.String(length=20), nullable=True),
        sa.Column("merchant_unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("agent_unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("merchant_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merchant_delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_alert_pending", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("handoff_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_admin_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference", name="uq_support_chat_conversation_reference"),
    )
    op.create_index("ix_support_chat_conversations_company_id", "support_chat_conversations", ["company_id"])
    op.create_index("ix_support_chat_conversations_store_id", "support_chat_conversations", ["store_id"])
    op.create_index("ix_support_chat_conversations_user_id", "support_chat_conversations", ["user_id"])
    op.create_index(
        "ix_support_chat_conversation_company_activity",
        "support_chat_conversations",
        ["company_id", "last_message_at"],
    )
    op.create_index(
        "ix_support_chat_conversation_status_activity",
        "support_chat_conversations",
        ["status", "last_message_at"],
    )
    op.create_index(
        "ix_support_chat_conversation_assigned",
        "support_chat_conversations",
        ["assigned_admin_id", "last_message_at"],
    )

    op.create_table(
        "support_chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_type", sa.String(length=20), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="text"),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("attachment_url", sa.String(length=500), nullable=True),
        sa.Column("attachment_name", sa.String(length=255), nullable=True),
        sa.Column("attachment_content_type", sa.String(length=100), nullable=True),
        sa.Column("attachment_byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("guide_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["support_chat_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_chat_messages_conversation_id", "support_chat_messages", ["conversation_id"])
    op.create_index("ix_support_chat_messages_seq", "support_chat_messages", ["seq"], unique=True)
    op.create_index(
        "ix_support_chat_message_conversation_created",
        "support_chat_messages",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_support_chat_message_conversation_seq",
        "support_chat_messages",
        ["conversation_id", "seq"],
    )


def downgrade() -> None:
    op.drop_index("ix_support_chat_message_conversation_seq", table_name="support_chat_messages")
    op.drop_index("ix_support_chat_message_conversation_created", table_name="support_chat_messages")
    op.drop_index("ix_support_chat_messages_seq", table_name="support_chat_messages")
    op.drop_index("ix_support_chat_messages_conversation_id", table_name="support_chat_messages")
    op.drop_table("support_chat_messages")
    op.drop_index("ix_support_chat_conversation_assigned", table_name="support_chat_conversations")
    op.drop_index("ix_support_chat_conversation_status_activity", table_name="support_chat_conversations")
    op.drop_index("ix_support_chat_conversation_company_activity", table_name="support_chat_conversations")
    op.drop_index("ix_support_chat_conversations_user_id", table_name="support_chat_conversations")
    op.drop_index("ix_support_chat_conversations_store_id", table_name="support_chat_conversations")
    op.drop_index("ix_support_chat_conversations_company_id", table_name="support_chat_conversations")
    op.drop_table("support_chat_conversations")
