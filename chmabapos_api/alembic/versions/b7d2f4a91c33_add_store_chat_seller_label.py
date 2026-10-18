"""Let the seller name a chat thread.

Anonymous visitors arrive in the inbox as "Guest"; the guest's own name is only
present when they choose to type one. A store-side label lets staff tell threads
apart. It is internal - the customer never sees it.

Revision ID: b7d2f4a91c33
Revises: c9e4a1b7d2f6
Create Date: 2026-10-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d2f4a91c33"
down_revision: Union[str, None] = "c9e4a1b7d2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("store_chat_conversations", sa.Column("seller_label", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("store_chat_conversations", "seller_label")
