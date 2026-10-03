"""add_warranty_claims

Warranty-claim lifecycle (docs/warranty-claim-plan.md): a claim on a sold
serial plus an append-only event log.

Revision ID: f2b3c4d5e6a7
Revises: a8b7c6d5e4f3
Create Date: 2026-10-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f2b3c4d5e6a7'
down_revision: Union[str, None] = 'a8b7c6d5e4f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'warranty_claims',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('claim_number', sa.String(length=32), nullable=False),
        sa.Column('serial_id', sa.UUID(), nullable=False),
        sa.Column('customer_id', sa.UUID(), nullable=True),
        sa.Column('order_id', sa.UUID(), nullable=True),
        sa.Column('order_item_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('resolution', sa.String(length=20), nullable=True),
        sa.Column('issue', sa.String(length=180), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('cost', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('replacement_serial_id', sa.UUID(), nullable=True),
        sa.Column('refund_id', sa.UUID(), nullable=True),
        sa.Column('service_ticket_id', sa.UUID(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decided_by', sa.UUID(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['serial_id'], ['product_serials.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_item_id'], ['order_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['replacement_serial_id'], ['product_serials.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['refund_id'], ['refunds.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['service_ticket_id'], ['serial_service_tickets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_warranty_claims_company_id'), 'warranty_claims', ['company_id'], unique=False)
    op.create_index(op.f('ix_warranty_claims_store_id'), 'warranty_claims', ['store_id'], unique=False)
    op.create_index(op.f('ix_warranty_claims_serial_id'), 'warranty_claims', ['serial_id'], unique=False)
    op.create_index('ix_warranty_claim_store_created', 'warranty_claims', ['store_id', 'claimed_at'], unique=False)

    op.create_table(
        'warranty_claim_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('claim_id', sa.UUID(), nullable=False),
        sa.Column('from_status', sa.String(length=20), nullable=True),
        sa.Column('to_status', sa.String(length=20), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('actor_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['claim_id'], ['warranty_claims.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_warranty_claim_events_claim_id'), 'warranty_claim_events', ['claim_id'], unique=False)
    op.create_index('ix_warranty_claim_event_claim_created', 'warranty_claim_events', ['claim_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_warranty_claim_event_claim_created', table_name='warranty_claim_events')
    op.drop_index(op.f('ix_warranty_claim_events_claim_id'), table_name='warranty_claim_events')
    op.drop_table('warranty_claim_events')
    op.drop_index('ix_warranty_claim_store_created', table_name='warranty_claims')
    op.drop_index(op.f('ix_warranty_claims_serial_id'), table_name='warranty_claims')
    op.drop_index(op.f('ix_warranty_claims_store_id'), table_name='warranty_claims')
    op.drop_index(op.f('ix_warranty_claims_company_id'), table_name='warranty_claims')
    op.drop_table('warranty_claims')
