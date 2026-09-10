"""add billing receipts

Issues an immutable ``billing_receipts`` row per successful plan payment, with a
human receipt number drawn from ``billing_receipt_number_seq``.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-10 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS billing_receipt_number_seq")
    op.create_table(
        'billing_receipts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('receipt_number', sa.String(length=32), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('subscription_id', sa.Uuid(), nullable=False),
        sa.Column('billing_payment_id', sa.Uuid(), nullable=False),
        sa.Column('plan_code', sa.String(length=20), nullable=False),
        sa.Column('billing_cycle', sa.String(length=20), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency_code', sa.String(length=3), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['billing_payment_id'], ['billing_payments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_billing_receipts_receipt_number'), 'billing_receipts', ['receipt_number'], unique=True)
    op.create_index(op.f('ix_billing_receipts_company_id'), 'billing_receipts', ['company_id'], unique=False)
    op.create_index(op.f('ix_billing_receipts_subscription_id'), 'billing_receipts', ['subscription_id'], unique=False)
    op.create_index(op.f('ix_billing_receipts_billing_payment_id'), 'billing_receipts', ['billing_payment_id'], unique=False)
    op.create_index('ix_billing_receipt_company_created', 'billing_receipts', ['company_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_billing_receipt_company_created', table_name='billing_receipts')
    op.drop_index(op.f('ix_billing_receipts_billing_payment_id'), table_name='billing_receipts')
    op.drop_index(op.f('ix_billing_receipts_subscription_id'), table_name='billing_receipts')
    op.drop_index(op.f('ix_billing_receipts_company_id'), table_name='billing_receipts')
    op.drop_index(op.f('ix_billing_receipts_receipt_number'), table_name='billing_receipts')
    op.drop_table('billing_receipts')
    op.execute("DROP SEQUENCE IF EXISTS billing_receipt_number_seq")
