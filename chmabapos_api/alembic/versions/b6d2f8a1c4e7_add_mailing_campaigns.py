"""Mailing campaigns, so the delivery log can be grouped.

A manual send now creates one `mailing_campaigns` row and stamps every
`email_sends` row with its id. Drip sends and one-off tests keep a null
campaign id. Deleting a campaign (not exposed yet) leaves its sends untouched.

Revision ID: b6d2f8a1c4e7
Revises: 9b7c5e1a2d4f
Create Date: 2026-10-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b6d2f8a1c4e7"
down_revision: Union[str, None] = "9b7c5e1a2d4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mailing_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audience", sa.String(60), nullable=False),
        sa.Column("audience_label", sa.String(160), nullable=True),
        sa.Column("sent_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["template_id"], ["email_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sent_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mailing_campaign_created", "mailing_campaigns", ["created_at"])

    op.add_column("email_sends", sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_email_sends_campaign_id",
        "email_sends",
        "mailing_campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_email_send_campaign", "email_sends", ["campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_email_send_campaign", table_name="email_sends")
    op.drop_constraint("fk_email_sends_campaign_id", "email_sends", type_="foreignkey")
    op.drop_column("email_sends", "campaign_id")
    op.drop_index("ix_mailing_campaign_created", table_name="mailing_campaigns")
    op.drop_table("mailing_campaigns")
