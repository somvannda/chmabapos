"""drop_plan_marketing_features

Marketing bullets are now derived from structured plan fields
(max_stores / max_members / transaction_limit / capabilities) and are no
longer stored on the plan row.

Revision ID: d5e9f1a2b3c4
Revises: e6f4a8c2d1b9
Create Date: 2026-09-09 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5e9f1a2b3c4'
down_revision: Union[str, None] = 'e6f4a8c2d1b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('plans', 'marketing_features')


def downgrade() -> None:
    op.add_column('plans', sa.Column('marketing_features', sa.JSON(), nullable=False, server_default='[]'))
