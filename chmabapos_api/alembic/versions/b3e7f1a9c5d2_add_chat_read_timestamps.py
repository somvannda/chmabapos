"""Read timestamps per side, so a message can show "Seen".

The conversation already tracks an unread *count* per side, which says how many
messages are waiting but not *when* the other side last looked. A timestamp per
side lets a client mark the reader's own last message seen - which is what stops
a shopper repeating a question the store has already read.

Revision ID: b3e7f1a9c5d2
Revises: a9c4e1f7b2d5
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3e7f1a9c5d2"
down_revision: Union[str, None] = "a9c4e1f7b2d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("store_chat_conversations", sa.Column("customer_read_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("store_chat_conversations", sa.Column("seller_read_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("store_chat_conversations", "seller_read_at")
    op.drop_column("store_chat_conversations", "customer_read_at")
