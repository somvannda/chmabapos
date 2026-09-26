"""narrow_product_image

Revision ID: d0e1f2a3b4c5
Revises: c9d8e7f6a5b4
Create Date: 2026-09-26 01:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d8e7f6a5b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Product images are now stored as /media/... URLs. Legacy inline base64
    # data URIs are cleared rather than truncated (a truncated image is useless).
    op.alter_column(
        'products',
        'image',
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
        postgresql_using="CASE WHEN image LIKE 'data:%%' THEN NULL ELSE left(image, 500) END",
    )


def downgrade() -> None:
    op.alter_column('products', 'image', existing_type=sa.String(length=500), type_=sa.Text(), existing_nullable=True)
