"""add_serial_service_tickets

Revision ID: c1d2e3f4a5b6
Revises: a1f2b3c4d5e6
Create Date: 2026-09-27 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'a1f2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'serial_service_tickets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('serial_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('store_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ticket_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('summary', sa.String(length=180), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('cost', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['serial_id'], ['product_serials.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_serial_service_tickets_company_id', 'serial_service_tickets', ['company_id'])
    op.create_index('ix_serial_service_tickets_serial_id', 'serial_service_tickets', ['serial_id'])
    op.create_index('ix_serial_ticket_serial_created', 'serial_service_tickets', ['serial_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_serial_ticket_serial_created', table_name='serial_service_tickets')
    op.drop_index('ix_serial_service_tickets_serial_id', table_name='serial_service_tickets')
    op.drop_index('ix_serial_service_tickets_company_id', table_name='serial_service_tickets')
    op.drop_table('serial_service_tickets')
