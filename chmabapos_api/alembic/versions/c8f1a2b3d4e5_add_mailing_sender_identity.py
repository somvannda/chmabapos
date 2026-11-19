"""Store the sender identity chosen for a mailing.

A campaign can go out as a different address than the platform default (for
example ``hello@`` versus ``billing@``) and replies are routed to a monitored
inbox with ``Reply-To``. The queue drains hours after a campaign is composed, so
the identity has to live on the row that is actually sent, not only in the
request.

Revision ID: c8f1a2b3d4e5
Revises: b7e4c2a9d1f6
Create Date: 2026-11-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8f1a2b3d4e5"
down_revision: Union[str, None] = "b7e4c2a9d1f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("email_sends", "mailing_campaigns"):
        op.add_column(table, sa.Column("from_address", sa.String(length=320), nullable=True))
        op.add_column(table, sa.Column("from_name", sa.String(length=120), nullable=True))
        op.add_column(table, sa.Column("reply_to", sa.String(length=320), nullable=True))


def downgrade() -> None:
    for table in ("email_sends", "mailing_campaigns"):
        op.drop_column(table, "reply_to")
        op.drop_column(table, "from_name")
        op.drop_column(table, "from_address")
