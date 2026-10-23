"""Record every click, not just the first URL per send.

Resend's `email.clicked` event carries the link, IP and user agent. One row per
event lets campaign reports rank links by actual clicks. Existing first-click
URLs are backfilled so old campaigns keep their top-link data.

Revision ID: d1f3a5b7c9e2
Revises: c9e2f4a6b8d1
Create Date: 2026-10-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d1f3a5b7c9e2"
down_revision: Union[str, None] = "c9e2f4a6b8d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_click_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("send_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(400), nullable=True),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["send_id"], ["email_sends.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["mailing_campaigns.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_click_send", "email_click_events", ["send_id"])
    op.create_index("ix_email_click_campaign", "email_click_events", ["campaign_id"])
    op.create_index("ix_email_click_time", "email_click_events", ["clicked_at"])
    # Keep the link history that only the first-click column preserved before.
    op.execute(
        "INSERT INTO email_click_events (id, send_id, campaign_id, url, clicked_at) "
        "SELECT gen_random_uuid(), id, campaign_id, clicked_url, clicked_at "
        "FROM email_sends WHERE clicked_url IS NOT NULL AND clicked_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_email_click_time", table_name="email_click_events")
    op.drop_index("ix_email_click_campaign", table_name="email_click_events")
    op.drop_index("ix_email_click_send", table_name="email_click_events")
    op.drop_table("email_click_events")
