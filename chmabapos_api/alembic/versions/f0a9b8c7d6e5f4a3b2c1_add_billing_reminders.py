"""add_billing_reminders

Tracks which expiry reminders (7 / 3 / 1 days before a paid plan's period
ends) have already been sent per subscription, so the daily job does not
re-send the same reminder.

Revision ID: f0a9b8c7d6e5f4a3b2c1
Revises: e9b8d7c6a5f4e3d2b1c0
Create Date: 2026-09-10 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f0a9b8c7d6e5f4a3b2c1'
down_revision: Union[str, None] = 'e9b8d7c6a5f4e3d2b1c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'billing_reminders',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('subscription_id', sa.Uuid(), nullable=False),
        sa.Column('days_before', sa.Integer(), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subscription_id', 'days_before', name='uq_billing_reminder_subscription_days'),
    )
    op.create_index(op.f('ix_billing_reminders_subscription_id'), 'billing_reminders', ['subscription_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_billing_reminders_subscription_id'), table_name='billing_reminders')
    op.drop_table('billing_reminders')
