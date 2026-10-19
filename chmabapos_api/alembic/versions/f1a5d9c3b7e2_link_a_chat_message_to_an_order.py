"""Link a chat message to an order, for order cards.

"Where is my order?" is the likeliest question in store chat. A message that
carries an order lets the store answer by sending a card the customer can open,
instead of a number they have to hunt for.

Revision ID: f1a5d9c3b7e2
Revises: e2b6c4a8f1d3
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a5d9c3b7e2"
down_revision: Union[str, None] = "e2b6c4a8f1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "store_chat_messages",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("store_chat_messages", "order_id")
