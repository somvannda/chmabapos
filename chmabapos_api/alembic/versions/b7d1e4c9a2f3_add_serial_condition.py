"""add_serial_condition

Per-unit condition data for serialized products (used / refurbished
electronics): cosmetic grade, battery health, a JSON scorecard, the supplier and
purchase-order lot a unit came from, and the current grader. Adds an append-only
``serial_condition_history`` audit table so a unit can be re-graded without
losing its prior assessments.

Revision ID: b7d1e4c9a2f3
Revises: f3b7c1d9e2a4
Create Date: 2026-09-30 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d1e4c9a2f3'
down_revision: Union[str, None] = 'f3b7c1d9e2a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('product_serials', sa.Column('condition_grade', sa.String(length=20), nullable=True))
    op.add_column('product_serials', sa.Column('battery_health', sa.Integer(), nullable=True))
    op.add_column('product_serials', sa.Column('battery_cycle_count', sa.Integer(), nullable=True))
    op.add_column('product_serials', sa.Column('condition_report', sa.JSON(), nullable=True))
    op.add_column('product_serials', sa.Column('supplier_id', sa.UUID(), nullable=True))
    op.add_column('product_serials', sa.Column('purchase_order_id', sa.UUID(), nullable=True))
    op.add_column('product_serials', sa.Column('graded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('product_serials', sa.Column('graded_by', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_product_serials_supplier_id', 'product_serials', 'suppliers', ['supplier_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_product_serials_purchase_order_id', 'product_serials', 'purchase_orders', ['purchase_order_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_product_serials_graded_by', 'product_serials', 'users', ['graded_by'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_product_serials_condition_grade'), 'product_serials', ['condition_grade'], unique=False)
    op.create_index(op.f('ix_product_serials_supplier_id'), 'product_serials', ['supplier_id'], unique=False)

    op.create_table(
        'serial_condition_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('serial_id', sa.UUID(), nullable=False),
        sa.Column('condition_grade', sa.String(length=20), nullable=True),
        sa.Column('battery_health', sa.Integer(), nullable=True),
        sa.Column('battery_cycle_count', sa.Integer(), nullable=True),
        sa.Column('condition_report', sa.JSON(), nullable=True),
        sa.Column('graded_by', sa.UUID(), nullable=True),
        sa.Column('graded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['serial_id'], ['product_serials.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['graded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_serial_condition_history_company_id'), 'serial_condition_history', ['company_id'], unique=False)
    op.create_index(op.f('ix_serial_condition_history_serial_id'), 'serial_condition_history', ['serial_id'], unique=False)
    op.create_index('ix_serial_condition_serial_graded', 'serial_condition_history', ['serial_id', 'graded_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_serial_condition_serial_graded', table_name='serial_condition_history')
    op.drop_index(op.f('ix_serial_condition_history_serial_id'), table_name='serial_condition_history')
    op.drop_index(op.f('ix_serial_condition_history_company_id'), table_name='serial_condition_history')
    op.drop_table('serial_condition_history')

    op.drop_index(op.f('ix_product_serials_supplier_id'), table_name='product_serials')
    op.drop_index(op.f('ix_product_serials_condition_grade'), table_name='product_serials')
    op.drop_constraint('fk_product_serials_graded_by', 'product_serials', type_='foreignkey')
    op.drop_constraint('fk_product_serials_purchase_order_id', 'product_serials', type_='foreignkey')
    op.drop_constraint('fk_product_serials_supplier_id', 'product_serials', type_='foreignkey')
    op.drop_column('product_serials', 'graded_by')
    op.drop_column('product_serials', 'graded_at')
    op.drop_column('product_serials', 'purchase_order_id')
    op.drop_column('product_serials', 'supplier_id')
    op.drop_column('product_serials', 'condition_report')
    op.drop_column('product_serials', 'battery_cycle_count')
    op.drop_column('product_serials', 'battery_health')
    op.drop_column('product_serials', 'condition_grade')
