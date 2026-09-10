"""add billing payment snapshots and capacity actions

Hardens the prepaid billing engine:

* ``billing_payments`` gains an immutable purchase snapshot (``company_id``,
  ``plan_code``, ``billing_cycle``, ``period_start``, ``period_end``) plus
  ``fulfilled_at`` as the durable idempotency guard, and a unique
  ``(provider, external_id)`` constraint so a replayed provider reference can
  never be fulfilled twice.
* new ``subscription_capacity_actions`` table records every forced store/member
  pause and restore, making capacity changes auditable and reversible.

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-09-10 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('billing_payments', sa.Column('company_id', sa.Uuid(), nullable=True))
    op.add_column('billing_payments', sa.Column('plan_code', sa.String(length=20), nullable=True))
    op.add_column('billing_payments', sa.Column('billing_cycle', sa.String(length=20), nullable=True))
    op.add_column('billing_payments', sa.Column('period_start', sa.DateTime(timezone=True), nullable=True))
    op.add_column('billing_payments', sa.Column('period_end', sa.DateTime(timezone=True), nullable=True))
    op.add_column('billing_payments', sa.Column('fulfilled_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_billing_payments_company_id'), 'billing_payments', ['company_id'], unique=False)
    op.create_foreign_key(
        'fk_billing_payments_company_id',
        'billing_payments',
        'companies',
        ['company_id'],
        ['id'],
        ondelete='CASCADE',
    )

    # Backfill the immutable snapshot from the subscription each payment paid.
    op.execute(
        """
        UPDATE billing_payments AS bp
        SET company_id = s.company_id,
            plan_code = s.plan_code,
            billing_cycle = s.billing_cycle
        FROM subscriptions AS s
        WHERE s.id = bp.subscription_id
        """
    )

    op.create_unique_constraint(
        'uq_billing_payment_provider_external',
        'billing_payments',
        ['provider', 'external_id'],
    )

    op.create_table(
        'subscription_capacity_actions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('subscription_id', sa.Uuid(), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('resource_type', sa.String(length=20), nullable=False),
        sa.Column('resource_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.String(length=40), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('restored_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_subscription_capacity_actions_subscription_id'),
        'subscription_capacity_actions',
        ['subscription_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_subscription_capacity_actions_company_id'),
        'subscription_capacity_actions',
        ['company_id'],
        unique=False,
    )
    op.create_index(
        'ix_capacity_action_company_created',
        'subscription_capacity_actions',
        ['company_id', 'created_at'],
        unique=False,
    )
    op.create_index(
        'ix_capacity_action_subscription_resource',
        'subscription_capacity_actions',
        ['subscription_id', 'resource_type', 'resource_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_capacity_action_subscription_resource', table_name='subscription_capacity_actions')
    op.drop_index('ix_capacity_action_company_created', table_name='subscription_capacity_actions')
    op.drop_index(op.f('ix_subscription_capacity_actions_company_id'), table_name='subscription_capacity_actions')
    op.drop_index(op.f('ix_subscription_capacity_actions_subscription_id'), table_name='subscription_capacity_actions')
    op.drop_table('subscription_capacity_actions')

    op.drop_constraint('uq_billing_payment_provider_external', 'billing_payments', type_='unique')
    op.drop_constraint('fk_billing_payments_company_id', 'billing_payments', type_='foreignkey')
    op.drop_index(op.f('ix_billing_payments_company_id'), table_name='billing_payments')
    op.drop_column('billing_payments', 'fulfilled_at')
    op.drop_column('billing_payments', 'period_end')
    op.drop_column('billing_payments', 'period_start')
    op.drop_column('billing_payments', 'billing_cycle')
    op.drop_column('billing_payments', 'plan_code')
    op.drop_column('billing_payments', 'company_id')
