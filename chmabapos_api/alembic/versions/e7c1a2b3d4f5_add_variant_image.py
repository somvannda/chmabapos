"""add_variant_image

Revision ID: e7c1a2b3d4f5
Revises: c1d2e3f4a5b6
Create Date: 2026-09-27 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7c1a2b3d4f5'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('product_variants', sa.Column('image', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('product_variants', 'image')
