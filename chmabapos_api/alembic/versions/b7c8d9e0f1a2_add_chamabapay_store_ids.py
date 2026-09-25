"""add chamabapay store ids

Map each merchant (company/store) to its ChmabaPay store so KHQR payments route
to that merchant's own ABA PayWay account. Additive and nullable.

Revision ID: b7c8d9e0f1a2
Revises: e5f6a7b8c9d0
Create Date: 2026-09-25 04:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('chamabapay_store_id', sa.String(length=40), nullable=True))
    op.add_column('stores', sa.Column('chamabapay_store_id', sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column('stores', 'chamabapay_store_id')
    op.drop_column('companies', 'chamabapay_store_id')
