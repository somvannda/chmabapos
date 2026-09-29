"""add_mailing_send_queue

Turns ``email_sends`` into an outbox: queued rows carry attempt count and the
next retry time so a worker can drain them with backoff instead of sending
inside the HTTP request.

Revision ID: d2a5b8c1e4f7
Revises: c1f4a7b2d9e3
Create Date: 2026-09-29 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2a5b8c1e4f7'
down_revision: Union[str, None] = 'c1f4a7b2d9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('email_sends', sa.Column('provider', sa.String(length=30), nullable=True))
    op.add_column('email_sends', sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('email_sends', sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('email_sends', sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_email_send_queue', 'email_sends', ['status', 'next_attempt_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_email_send_queue', table_name='email_sends')
    op.drop_column('email_sends', 'last_attempt_at')
    op.drop_column('email_sends', 'next_attempt_at')
    op.drop_column('email_sends', 'attempts')
    op.drop_column('email_sends', 'provider')
