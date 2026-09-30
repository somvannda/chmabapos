"""split_supplier_customer_warranty

Splits the single ``product_serials.warranty_months`` / ``warranty_until`` pair
into two explicit warranties:

* supplier warranty, anchored to when the unit was received into stock, and
* customer warranty, anchored to when the unit was sold (``sold_at``).

Legacy rows are backfilled into the supplier columns because the old clock
started at receipt.

Revision ID: f3b7c1d9e2a4
Revises: d2a5b8c1e4f7
Create Date: 2026-09-30 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3b7c1d9e2a4'
down_revision: Union[str, None] = 'd2a5b8c1e4f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('product_serials', sa.Column('supplier_warranty_months', sa.Integer(), nullable=True))
    op.add_column('product_serials', sa.Column('supplier_warranty_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('product_serials', sa.Column('customer_warranty_months', sa.Integer(), nullable=True))
    op.add_column('product_serials', sa.Column('customer_warranty_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('product_serials', sa.Column('sold_at', sa.DateTime(timezone=True), nullable=True))
    # The old warranty clock started at receipt, so it maps to the supplier side.
    op.execute(
        "UPDATE product_serials "
        "SET supplier_warranty_months = warranty_months, "
        "supplier_warranty_until = warranty_until"
    )
    op.drop_column('product_serials', 'warranty_months')
    op.drop_column('product_serials', 'warranty_until')


def downgrade() -> None:
    op.add_column('product_serials', sa.Column('warranty_months', sa.Integer(), nullable=True))
    op.add_column('product_serials', sa.Column('warranty_until', sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE product_serials "
        "SET warranty_months = supplier_warranty_months, "
        "warranty_until = supplier_warranty_until"
    )
    op.drop_column('product_serials', 'sold_at')
    op.drop_column('product_serials', 'customer_warranty_until')
    op.drop_column('product_serials', 'customer_warranty_months')
    op.drop_column('product_serials', 'supplier_warranty_until')
    op.drop_column('product_serials', 'supplier_warranty_months')
