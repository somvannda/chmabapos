"""Quote an earlier message in a store chat.

A reply keeps the quoted message's id so both clients can render the snippet.
``SET NULL`` on the foreign key means a removed message leaves the reply intact,
just without a quote block - the message itself is the record that matters.

Revision ID: 276f72e82622
Revises: f4d2a8c6e1b3
Create Date: 2026-10-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "276f72e82622"
down_revision: Union[str, None] = "f4d2a8c6e1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("store_chat_messages", sa.Column("reply_to_message_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_store_chat_messages_reply_to",
        "store_chat_messages",
        "store_chat_messages",
        ["reply_to_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_store_chat_message_reply_to", "store_chat_messages", ["reply_to_message_id"])


def downgrade() -> None:
    op.drop_index("ix_store_chat_message_reply_to", table_name="store_chat_messages")
    op.drop_constraint("fk_store_chat_messages_reply_to", "store_chat_messages", type_="foreignkey")
    op.drop_column("store_chat_messages", "reply_to_message_id")
