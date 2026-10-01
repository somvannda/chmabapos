"""add_support_conversations

Adds ``support_conversations`` and ``support_messages``: the persisted transcript
of in-app support chats. Answer feedback already lives on ``platform_activities``;
this stores the conversation itself so a user can resume and support has context.

Revision ID: b1d2e3f4a5c6
Revises: e8f2a4b6c0d1
Create Date: 2026-10-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b1d2e3f4a5c6'
down_revision: Union[str, None] = 'e8f2a4b6c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'support_conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_support_conversation_user_updated', 'support_conversations', ['user_id', 'updated_at'])
    op.create_index('ix_support_conversations_company_id', 'support_conversations', ['company_id'])
    op.create_index('ix_support_conversations_user_id', 'support_conversations', ['user_id'])

    op.create_table(
        'support_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('guide_ids', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['support_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_support_message_conversation_created', 'support_messages', ['conversation_id', 'created_at'])
    op.create_index('ix_support_messages_conversation_id', 'support_messages', ['conversation_id'])


def downgrade() -> None:
    op.drop_index('ix_support_messages_conversation_id', table_name='support_messages')
    op.drop_index('ix_support_message_conversation_created', table_name='support_messages')
    op.drop_table('support_messages')
    op.drop_index('ix_support_conversations_user_id', table_name='support_conversations')
    op.drop_index('ix_support_conversations_company_id', table_name='support_conversations')
    op.drop_index('ix_support_conversation_user_updated', table_name='support_conversations')
    op.drop_table('support_conversations')
