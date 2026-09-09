"""add_subscription_scheduling_fields

Stores an owner's scheduled plan change on the governing subscription:
``scheduled_plan_code`` is the target plan (a paid plan to renew at, or
``free`` to cancel) and the keep-lists capture which stores/members stay
active when a downgrade to a smaller plan takes effect at ``ends_at``.

Revision ID: d7a9c2f5b8e3a1f0d6c4
Revises: d5e9f1a2b3c4
Create Date: 2026-09-09 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd7a9c2f5b8e3a1f0d6c4'
down_revision: Union[str, None] = 'd5e9f1a2b3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('subscriptions', sa.Column('scheduled_plan_code', sa.String(length=20), nullable=True))
    op.add_column('subscriptions', sa.Column('scheduled_store_ids', sa.JSON(), nullable=True))
    op.add_column('subscriptions', sa.Column('scheduled_member_ids', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('subscriptions', 'scheduled_member_ids')
    op.drop_column('subscriptions', 'scheduled_store_ids')
    op.drop_column('subscriptions', 'scheduled_plan_code')
