"""add_support_ticket_attachments

Adds ``support_ticket_attachments``: reference images (screenshots) attached to
a support ticket's opening question or one of its thread messages. Rows are
created unowned (``ticket_id`` NULL) while an upload is being composed, then
claimed when the request or reply is submitted.

Revision ID: a7d3f1c9b2e4
Revises: f1e2d3c4b5a6
Create Date: 2026-10-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a7d3f1c9b2e4'
down_revision: Union[str, None] = 'f1e2d3c4b5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'support_ticket_attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ticket_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=True),
        sa.Column('byte_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['support_ticket_messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_support_ticket_attachment_ticket_created', 'support_ticket_attachments', ['ticket_id', 'created_at'])
    op.create_index('ix_support_ticket_attachment_message_id', 'support_ticket_attachments', ['message_id'])
    op.create_index('ix_support_ticket_attachments_company_id', 'support_ticket_attachments', ['company_id'])
    op.create_index('ix_support_ticket_attachments_ticket_id', 'support_ticket_attachments', ['ticket_id'])


def downgrade() -> None:
    op.drop_index('ix_support_ticket_attachments_ticket_id', table_name='support_ticket_attachments')
    op.drop_index('ix_support_ticket_attachments_company_id', table_name='support_ticket_attachments')
    op.drop_index('ix_support_ticket_attachment_message_id', table_name='support_ticket_attachments')
    op.drop_index('ix_support_ticket_attachment_ticket_created', table_name='support_ticket_attachments')
    op.drop_table('support_ticket_attachments')
