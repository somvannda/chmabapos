"""add_aba_payway_links

Revision ID: 1b2f6a0c9e3d
Revises: c8d4e2f6a9b1
Create Date: 2026-09-08 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1b2f6a0c9e3d'
down_revision: Union[str, None] = 'c8d4e2f6a9b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('aba_payway_link', sa.String(length=255), nullable=True))
    op.add_column('companies', sa.Column('aba_payway_status', sa.String(length=20), nullable=False, server_default='none'))
    op.add_column('stores', sa.Column('aba_payway_link', sa.String(length=255), nullable=True))
    op.add_column('stores', sa.Column('aba_payway_status', sa.String(length=20), nullable=False, server_default='none'))


def downgrade() -> None:
    op.drop_column('stores', 'aba_payway_status')
    op.drop_column('stores', 'aba_payway_link')
    op.drop_column('companies', 'aba_payway_status')
    op.drop_column('companies', 'aba_payway_link')
