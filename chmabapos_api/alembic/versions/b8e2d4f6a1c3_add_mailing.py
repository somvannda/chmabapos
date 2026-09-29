"""add_mailing

Admin Mailing tool: reusable email templates, a per-recipient delivery log,
and a suppression (unsubscribe) list so opted-out addresses are never mailed.

Revision ID: b8e2d4f6a1c3
Revises: c5e7f9a1b3d2
Create Date: 2026-09-29 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8e2d4f6a1c3'
down_revision: Union[str, None] = 'c5e7f9a1b3d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_templates',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('subject', sa.String(length=300), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'email_sends',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('template_id', sa.Uuid(), nullable=True),
        sa.Column('recipient_email', sa.String(length=320), nullable=False),
        sa.Column('subject', sa.String(length=300), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('sent_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['template_id'], ['email_templates.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sent_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_email_send_created', 'email_sends', ['created_at'], unique=False)
    op.create_index('ix_email_send_user', 'email_sends', ['user_id'], unique=False)
    op.create_index('ix_email_send_recipient', 'email_sends', ['recipient_email'], unique=False)

    op.create_table(
        'email_suppressions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('reason', sa.String(length=60), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_email_suppressions_email', 'email_suppressions', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_email_suppressions_email', table_name='email_suppressions')
    op.drop_table('email_suppressions')
    op.drop_index('ix_email_send_recipient', table_name='email_sends')
    op.drop_index('ix_email_send_user', table_name='email_sends')
    op.drop_index('ix_email_send_created', table_name='email_sends')
    op.drop_table('email_sends')
    op.drop_table('email_templates')
