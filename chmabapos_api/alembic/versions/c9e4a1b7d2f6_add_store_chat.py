"""Storefront customer <-> store chat.

Adds the three tables behind the storefront chat widget: the conversation (keyed
by an unguessable visitor token for guests, or a shopper account for signed-in
customers), its messages, and emoji reactions.

``store_chat_messages.seq`` is a database identity column used as the realtime
cursor: it is monotonic within the table, so a stream can resume with
``after_seq`` without relying on timestamp ties.

Revision ID: c9e4a1b7d2f6
Revises: a8f4c2e6b9d3
Create Date: 2026-10-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9e4a1b7d2f6"
down_revision: Union[str, None] = "a8f4c2e6b9d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "store_chat_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shopper_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("visitor_token", sa.String(length=64), nullable=False),
        sa.Column("guest_name", sa.String(length=120), nullable=True),
        sa.Column("guest_email", sa.String(length=320), nullable=True),
        sa.Column("guest_phone", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_preview", sa.String(length=200), nullable=True),
        sa.Column("last_message_author", sa.String(length=20), nullable=True),
        sa.Column("seller_unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("customer_unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shopper_id"], ["shopper_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("visitor_token", name="uq_store_chat_visitor_token"),
    )
    op.create_index("ix_store_chat_conversations_company_id", "store_chat_conversations", ["company_id"])
    op.create_index("ix_store_chat_conversations_store_id", "store_chat_conversations", ["store_id"])
    op.create_index("ix_store_chat_conversations_shopper_id", "store_chat_conversations", ["shopper_id"])
    op.create_index("ix_store_chat_conversation_store_activity", "store_chat_conversations", ["store_id", "last_message_at"])
    op.create_index("ix_store_chat_conversation_company_activity", "store_chat_conversations", ["company_id", "last_message_at"])
    op.create_index("ix_store_chat_conversation_shopper_store", "store_chat_conversations", ["shopper_id", "store_id"])

    op.create_table(
        "store_chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_type", sa.String(length=20), nullable=False),
        sa.Column("sender_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sender_shopper_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="text"),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("attachment_url", sa.String(length=500), nullable=True),
        sa.Column("attachment_name", sa.String(length=255), nullable=True),
        sa.Column("attachment_content_type", sa.String(length=100), nullable=True),
        sa.Column("attachment_byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attachment_duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["store_chat_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sender_shopper_id"], ["shopper_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_store_chat_messages_conversation_id", "store_chat_messages", ["conversation_id"])
    op.create_index("ix_store_chat_messages_seq", "store_chat_messages", ["seq"], unique=True)
    op.create_index("ix_store_chat_message_conversation_created", "store_chat_messages", ["conversation_id", "created_at"])
    op.create_index("ix_store_chat_message_conversation_seq", "store_chat_messages", ["conversation_id", "seq"])

    op.create_table(
        "store_chat_reactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reactor_type", sa.String(length=20), nullable=False),
        sa.Column("reactor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reactor_shopper_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("emoji", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["store_chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reactor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reactor_shopper_id"], ["shopper_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "reactor_type", "emoji", name="uq_store_chat_reaction"),
    )
    op.create_index("ix_store_chat_reactions_message_id", "store_chat_reactions", ["message_id"])
    op.create_index("ix_store_chat_reaction_message", "store_chat_reactions", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_store_chat_reaction_message", table_name="store_chat_reactions")
    op.drop_index("ix_store_chat_reactions_message_id", table_name="store_chat_reactions")
    op.drop_table("store_chat_reactions")
    op.drop_index("ix_store_chat_message_conversation_seq", table_name="store_chat_messages")
    op.drop_index("ix_store_chat_message_conversation_created", table_name="store_chat_messages")
    op.drop_index("ix_store_chat_messages_seq", table_name="store_chat_messages")
    op.drop_index("ix_store_chat_messages_conversation_id", table_name="store_chat_messages")
    op.drop_table("store_chat_messages")
    op.drop_index("ix_store_chat_conversation_shopper_store", table_name="store_chat_conversations")
    op.drop_index("ix_store_chat_conversation_company_activity", table_name="store_chat_conversations")
    op.drop_index("ix_store_chat_conversation_store_activity", table_name="store_chat_conversations")
    op.drop_index("ix_store_chat_conversations_shopper_id", table_name="store_chat_conversations")
    op.drop_index("ix_store_chat_conversations_store_id", table_name="store_chat_conversations")
    op.drop_index("ix_store_chat_conversations_company_id", table_name="store_chat_conversations")
    op.drop_table("store_chat_conversations")
