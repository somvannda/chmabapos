"""Record when the store was last alerted about an unanswered chat.

A customer message that nobody answers is the failure mode this feature must not
have, and the in-app bell only helps someone already looking at the app. A scan
queues an email to the owner/manager when a thread has sat unanswered; this column
is the marker that stops a repeated scan sending the same alert twice.

Revision ID: c3f8a1d6e4b7
Revises: b7d2f4a91c33
Create Date: 2026-10-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3f8a1d6e4b7"
down_revision: Union[str, None] = "b7d2f4a91c33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "store_chat_conversations",
        sa.Column("seller_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("store_chat_conversations", "seller_notified_at")
