"""Record when the customer was last emailed about a store reply.

A guest who gave an email loses the thread if they clear their browser, and will
not see a reply with the tab closed. A note that the store replied brings them
back. This marker throttles it: one email per quiet period per thread, not one
per message.

Revision ID: d7a3f8c1e5b9
Revises: c5d9e2f8a1b4
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7a3f8c1e5b9"
down_revision: Union[str, None] = "c5d9e2f8a1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "store_chat_conversations",
        sa.Column("customer_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("store_chat_conversations", "customer_notified_at")
