"""add is_sample to products

Marks the demo rows seeded into a brand-new workspace. They are sellable so a
merchant can try the register immediately, but they must never count as "the
merchant added a product" in the setup checklist or the activation funnel.

Revision ID: f4a1b2c3d4e5
Revises: d4a7b1e9c2f6
Create Date: 2026-10-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a1b2c3d4e5"
down_revision: Union[str, None] = "d4a7b1e9c2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("products", "is_sample", server_default=None)


def downgrade() -> None:
    op.drop_column("products", "is_sample")
