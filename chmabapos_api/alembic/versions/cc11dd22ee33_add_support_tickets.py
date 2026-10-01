"""add_support_tickets

Adds ``support_tickets``: a merchant support request tracked from escalation to
closure, so the merchant can be told when it is resolved.

Revision ID: cc11dd22ee33
Revises: b5c6d7e8f9a0
Create Date: 2026-10-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'cc11dd22ee33'
down_revision: Union[str, None] = 'b5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'support_tickets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reference', sa.String(length=20), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('store_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference', name='uq_support_ticket_reference'),
    )
    op.create_index('ix_support_ticket_company_created', 'support_tickets', ['company_id', 'created_at'])
    op.create_index('ix_support_ticket_status_created', 'support_tickets', ['status', 'created_at'])
    op.create_index('ix_support_tickets_company_id', 'support_tickets', ['company_id'])
    op.create_index('ix_support_tickets_user_id', 'support_tickets', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_support_tickets_user_id', table_name='support_tickets')
    op.drop_index('ix_support_tickets_company_id', table_name='support_tickets')
    op.drop_index('ix_support_ticket_status_created', table_name='support_tickets')
    op.drop_index('ix_support_ticket_company_created', table_name='support_tickets')
    op.drop_table('support_tickets')
