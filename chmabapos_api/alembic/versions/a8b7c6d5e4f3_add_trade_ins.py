"""add_trade_ins

Trade-in / buyback (docs/trade-in-plan.md): a customer device accepted into
stock at an assessed value, optionally applied to a sale as a credit.

Revision ID: a8b7c6d5e4f3
Revises: e3b6c9d2f5a8
Create Date: 2026-10-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a8b7c6d5e4f3'
down_revision: Union[str, None] = 'e3b6c9d2f5a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'trade_ins',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('customer_id', sa.UUID(), nullable=True),
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('serial_id', sa.UUID(), nullable=True),
        sa.Column('order_id', sa.UUID(), nullable=True),
        sa.Column('serial_number', sa.String(length=120), nullable=False),
        sa.Column('imei', sa.String(length=40), nullable=True),
        sa.Column('condition_grade', sa.String(length=20), nullable=True),
        sa.Column('battery_health', sa.Integer(), nullable=True),
        sa.Column('condition_report', sa.JSON(), nullable=True),
        sa.Column('assessed_value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['serial_id'], ['product_serials.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_trade_ins_company_id'), 'trade_ins', ['company_id'], unique=False)
    op.create_index(op.f('ix_trade_ins_store_id'), 'trade_ins', ['store_id'], unique=False)
    op.create_index(op.f('ix_trade_ins_order_id'), 'trade_ins', ['order_id'], unique=False)
    op.create_index('ix_trade_in_store_created', 'trade_ins', ['store_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_trade_in_store_created', table_name='trade_ins')
    op.drop_index(op.f('ix_trade_ins_order_id'), table_name='trade_ins')
    op.drop_index(op.f('ix_trade_ins_store_id'), table_name='trade_ins')
    op.drop_index(op.f('ix_trade_ins_company_id'), table_name='trade_ins')
    op.drop_table('trade_ins')
