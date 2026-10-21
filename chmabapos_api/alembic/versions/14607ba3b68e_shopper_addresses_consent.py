"""Saved addresses and marketing consent for shoppers.

Marketing consent is stored on the account with the time it was last chosen; an
unsubscribe is also written to the platform suppression list by the endpoint.
Addresses cascade with the account, so deleting a shopper removes them.

Revision ID: 14607ba3b68e
Revises: 276f72e82622
Create Date: 2026-10-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "14607ba3b68e"
down_revision: Union[str, None] = "276f72e82622"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shopper_accounts", sa.Column("marketing_opt_in", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("shopper_accounts", sa.Column("marketing_opt_in_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "shopper_addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shopper_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(60), nullable=True),
        sa.Column("recipient_name", sa.String(160), nullable=False),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("line1", sa.String(200), nullable=False),
        sa.Column("line2", sa.String(200), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("state", sa.String(120), nullable=True),
        sa.Column("postal_code", sa.String(30), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="KH"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shopper_id"], ["shopper_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopper_address_shopper", "shopper_addresses", ["shopper_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_shopper_address_shopper", table_name="shopper_addresses")
    op.drop_table("shopper_addresses")
    op.drop_column("shopper_accounts", "marketing_opt_in_at")
    op.drop_column("shopper_accounts", "marketing_opt_in")
