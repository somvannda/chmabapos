"""add_email_delivery_events

Stores the provider message id and the delivery/open/click timestamps that
arrive on Resend (Svix) webhooks, so the mailing delivery log can show more than
"sent" once the webhook is configured.

Revision ID: e3b6c9d2f5a8
Revises: b9d1e3f5a7c2
Create Date: 2026-10-03 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e3b6c9d2f5a8'
down_revision: Union[str, None] = 'b9d1e3f5a7c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('email_sends', sa.Column('provider_message_id', sa.String(length=120), nullable=True))
    op.add_column('email_sends', sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('email_sends', sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('email_sends', sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('email_sends', sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_email_send_provider_message', 'email_sends', ['provider_message_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_email_send_provider_message', table_name='email_sends')
    op.drop_column('email_sends', 'last_event_at')
    op.drop_column('email_sends', 'clicked_at')
    op.drop_column('email_sends', 'opened_at')
    op.drop_column('email_sends', 'delivered_at')
    op.drop_column('email_sends', 'provider_message_id')
