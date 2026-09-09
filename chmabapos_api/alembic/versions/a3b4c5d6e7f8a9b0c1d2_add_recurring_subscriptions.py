"""add_recurring_subscriptions

Introduces the Paddle auto-renew billing model alongside the existing prepaid
(KHQR / one-time card) model:

* ``companies.paddle_customer_id`` links a workspace to its Paddle customer.
* ``recurring_subscriptions`` mirrors Paddle subscription state (webhook sync).
  While in force it is the workspace's governing plan; prepaid paid periods
  are forfeited the day it starts so a workspace never pays twice.

The prepaid ``subscriptions`` table and its lifecycle are untouched.

Revision ID: a3b4c5d6e7f8a9b0c1d2
Revises: f0a9b8c7d6e5f4a3b2c1
Create Date: 2026-09-10 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3b4c5d6e7f8a9b0c1d2'
down_revision: Union[str, None] = 'f0a9b8c7d6e5f4a3b2c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('paddle_customer_id', sa.String(length=255), nullable=True))
    op.create_unique_constraint('uq_companies_paddle_customer_id', 'companies', ['paddle_customer_id'])
    op.create_table(
        'recurring_subscriptions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('paddle_subscription_id', sa.String(length=255), nullable=False),
        sa.Column('paddle_customer_id', sa.String(length=255), nullable=True),
        sa.Column('price_id', sa.String(length=255), nullable=True),
        sa.Column('plan_code', sa.String(length=20), nullable=False),
        sa.Column('billing_cycle', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scheduled_action', sa.String(length=20), nullable=True),
        sa.Column('scheduled_effective_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scheduled_store_ids', sa.JSON(), nullable=True),
        sa.Column('scheduled_member_ids', sa.JSON(), nullable=True),
        sa.Column('paused_store_ids', sa.JSON(), nullable=True),
        sa.Column('paused_member_ids', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_code'], ['plans.code']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('paddle_subscription_id'),
    )
    op.create_index(
        op.f('ix_recurring_subscription_company_status'),
        'recurring_subscriptions',
        ['company_id', 'status'],
        unique=False,
    )
    op.create_index(
        op.f('ix_recurring_subscriptions_paddle_subscription_id'),
        'recurring_subscriptions',
        ['paddle_subscription_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_recurring_subscriptions_paddle_subscription_id'), table_name='recurring_subscriptions')
    op.drop_index(op.f('ix_recurring_subscription_company_status'), table_name='recurring_subscriptions')
    op.drop_table('recurring_subscriptions')
    op.drop_constraint('uq_companies_paddle_customer_id', 'companies', type_='unique')
    op.drop_column('companies', 'paddle_customer_id')
