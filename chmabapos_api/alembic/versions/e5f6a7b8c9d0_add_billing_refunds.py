"""add billing refunds

Support-only correction records for billing payments. Refunds never mutate the
original immutable payment and never change entitlement.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-10 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'billing_refunds',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('billing_payment_id', sa.Uuid(), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency_code', sa.String(length=3), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('provider_reference', sa.String(length=255), nullable=True),
        sa.Column('refunded_by', sa.Uuid(), nullable=True),
        sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['billing_payment_id'], ['billing_payments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['refunded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_billing_refunds_billing_payment_id'), 'billing_refunds', ['billing_payment_id'], unique=False)
    op.create_index(op.f('ix_billing_refunds_company_id'), 'billing_refunds', ['company_id'], unique=False)
    op.create_index('ix_billing_refund_company_created', 'billing_refunds', ['company_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_billing_refund_company_created', table_name='billing_refunds')
    op.drop_index(op.f('ix_billing_refunds_company_id'), table_name='billing_refunds')
    op.drop_index(op.f('ix_billing_refunds_billing_payment_id'), table_name='billing_refunds')
    op.drop_table('billing_refunds')
