"""add_support_ticket_messages

Adds ``support_ticket_messages``: the thread of a support ticket (merchant and
agent replies, plus a system note capturing the assistant context).

Revision ID: c3e4f5a6b7d8
Revises: d7e8f9a0b1c2
Create Date: 2026-10-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c3e4f5a6b7d8'
down_revision: Union[str, None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'support_ticket_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ticket_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('author_type', sa.String(length=20), nullable=False, server_default='agent'),
        sa.Column('author_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_support_ticket_message_ticket_created', 'support_ticket_messages', ['ticket_id', 'created_at'])
    op.create_index('ix_support_ticket_messages_ticket_id', 'support_ticket_messages', ['ticket_id'])


def downgrade() -> None:
    op.drop_index('ix_support_ticket_messages_ticket_id', table_name='support_ticket_messages')
    op.drop_index('ix_support_ticket_message_ticket_created', table_name='support_ticket_messages')
    op.drop_table('support_ticket_messages')
