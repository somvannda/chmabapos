"""Link a chat notification to its conversation, so reading the thread clears it.

A store chat message raised a bell notification with no link back to the
conversation. Opening the thread cleared the conversation's unread counter but
left the notification unread, so the bell kept announcing a thread that had
already been answered - and it was still unread after signing in again. The link
lets the thread's read/reply clear exactly the notification that belongs to it.

Revision ID: a9c4e1f7b2d5
Revises: f1a5d9c3b7e2
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9c4e1f7b2d5"
down_revision: Union[str, None] = "f1a5d9c3b7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("store_chat_conversations.id", ondelete="CASCADE"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notifications", "conversation_id")
