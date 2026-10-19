"""Link a chat message to a product, for product cards.

An order card answers "where is my order?"; a product card answers "is this the
one you meant?". Same mechanism, and the entry point is the product page itself.

Revision ID: a3c9e1f5b7d2
Revises: f2b8d4a6c1e9
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3c9e1f5b7d2"
down_revision: Union[str, None] = "f2b8d4a6c1e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "store_chat_messages",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("store_chat_messages", "product_id")
