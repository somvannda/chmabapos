"""Track when each side last received the thread, for a delivered tick.

The conversation already records when each side last *read* the thread. A single
tick needs one state before that: whether the other side's client has actually
received the message. ``delivered_at`` is stamped when that side fetches the
thread, so a message shows sent -> delivered -> seen instead of jumping straight
to "seen".

Revision ID: d8e1f4a7c2b9
Revises: c1f4a8d2e6b3
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8e1f4a7c2b9"
down_revision: Union[str, None] = "c1f4a8d2e6b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("store_chat_conversations", sa.Column("seller_delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("store_chat_conversations", sa.Column("customer_delivered_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("store_chat_conversations", "customer_delivered_at")
    op.drop_column("store_chat_conversations", "seller_delivered_at")
