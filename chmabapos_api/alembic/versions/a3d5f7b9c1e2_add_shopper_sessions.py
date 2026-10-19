"""Add revocable shopper sign-in sessions.

Shoppers had no server-side session, so a copied bearer token stayed usable until
it expired and signing out changed nothing. This table gives logout something to
revoke: the access token references a session by id, and a missing, expired or
revoked session fails authentication.

Additive: no existing row changes, and the storefront host is not live yet, so no
shopper is holding a token that this would invalidate.

Revision ID: a3d5f7b9c1e2
Revises: b4e6f8a0c2d3
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3d5f7b9c1e2"
down_revision: Union[str, None] = "b4e6f8a0c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shopper_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("shopper_id", sa.UUID(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_token_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["shopper_id"], ["shopper_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index("ix_shopper_sessions_shopper", "shopper_sessions", ["shopper_id"])


def downgrade() -> None:
    op.drop_index("ix_shopper_sessions_shopper", table_name="shopper_sessions")
    op.drop_table("shopper_sessions")
