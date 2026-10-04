"""add_reservations

Revision ID: f9e8d7c6b5a4
Revises: e9f0a1b2c3d4
Create Date: 2026-10-04 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f9e8d7c6b5a4'
down_revision: Union[str, None] = 'e9f0a1b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reservations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('kind', sa.String(length=20), server_default='reservation', nullable=False),
        sa.Column('customer_name', sa.String(length=160), nullable=False),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('party_size', sa.Integer(), server_default='2', nullable=False),
        sa.Column('reserved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), server_default='90', nullable=False),
        sa.Column('table_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='booked', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['table_id'], ['dining_tables.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reservations_store_id'), 'reservations', ['store_id'], unique=False)
    op.create_index('ix_reservation_store_time', 'reservations', ['store_id', 'reserved_at'], unique=False)
    op.create_index('ix_reservation_store_status', 'reservations', ['store_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_reservation_store_status', table_name='reservations')
    op.drop_index('ix_reservation_store_time', table_name='reservations')
    op.drop_index(op.f('ix_reservations_store_id'), table_name='reservations')
    op.drop_table('reservations')
