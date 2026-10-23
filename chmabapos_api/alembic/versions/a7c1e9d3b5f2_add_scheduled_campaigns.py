"""Scheduled campaigns.

Campaigns can be created ahead of time. Until the worker releases them they have
no `email_sends` rows; `released_at` marks the moment the audience was resolved
and queued, and `canceled_at` stops a pending campaign. Existing campaigns are
backfilled as already released.

Revision ID: a7c1e9d3b5f2
Revises: a3c4d5e6f7b8
Create Date: 2026-10-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c1e9d3b5f2"
down_revision: Union[str, None] = "a3c4d5e6f7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mailing_campaigns", sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mailing_campaigns", sa.Column("released_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mailing_campaigns", sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mailing_campaigns", sa.Column("min_age_hours", sa.Integer(), nullable=True))
    op.add_column("mailing_campaigns", sa.Column("max_age_days", sa.Integer(), nullable=True))
    op.add_column("mailing_campaigns", sa.Column("require_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("mailing_campaigns", sa.Column("send_limit", sa.Integer(), nullable=False, server_default="200"))
    op.create_index("ix_mailing_campaign_scheduled", "mailing_campaigns", ["scheduled_at"])
    # Every campaign that existed before this migration was sent immediately.
    op.execute("UPDATE mailing_campaigns SET released_at = created_at WHERE released_at IS NULL")


def downgrade() -> None:
    op.drop_index("ix_mailing_campaign_scheduled", table_name="mailing_campaigns")
    op.drop_column("mailing_campaigns", "send_limit")
    op.drop_column("mailing_campaigns", "require_consent")
    op.drop_column("mailing_campaigns", "max_age_days")
    op.drop_column("mailing_campaigns", "min_age_hours")
    op.drop_column("mailing_campaigns", "canceled_at")
    op.drop_column("mailing_campaigns", "released_at")
    op.drop_column("mailing_campaigns", "scheduled_at")
