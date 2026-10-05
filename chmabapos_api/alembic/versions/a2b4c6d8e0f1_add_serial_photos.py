"""add_serial_photos

Per-unit photos for serialized products: one ``product_serial_photos`` row per
image, so a one-of-a-kind unit can carry several pictures.

Revision ID: a2b4c6d8e0f1
Revises: f9e8d7c6b5a4
Create Date: 2026-10-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a2b4c6d8e0f1'
down_revision: Union[str, None] = 'f9e8d7c6b5a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_serial_photos',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('serial_id', sa.UUID(), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['serial_id'], ['product_serials.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_product_serial_photos_company_id'), 'product_serial_photos', ['company_id'], unique=False)
    op.create_index(op.f('ix_product_serial_photos_serial_id'), 'product_serial_photos', ['serial_id'], unique=False)
    op.create_index('ix_product_serial_photo_serial_position', 'product_serial_photos', ['serial_id', 'position'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_product_serial_photo_serial_position', table_name='product_serial_photos')
    op.drop_index(op.f('ix_product_serial_photos_serial_id'), table_name='product_serial_photos')
    op.drop_index(op.f('ix_product_serial_photos_company_id'), table_name='product_serial_photos')
    op.drop_table('product_serial_photos')
