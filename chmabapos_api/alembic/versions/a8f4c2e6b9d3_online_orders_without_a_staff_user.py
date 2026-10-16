"""Let an order exist without a staff user, so an online order can be one.

An order placed on a store page had no staff user behind it, and ``orders.created_by`` was
NOT NULL - which is the single reason those orders were parked as held tickets instead, and
therefore why a paid online sale did not appear in Orders or in reporting until somebody
settled the ticket by hand.

``source`` records where a sale came from so reports can tell a counter sale from an online
one without inferring it from whether a user is attached, and ``public_token`` gives the
shopper an unguessable handle on their own order, the same contract the ticket token had.

Revision ID: a8f4c2e6b9d3
Revises: f7c1a4b8d2e6
Create Date: 2026-10-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8f4c2e6b9d3"
down_revision: Union[str, None] = "f7c1a4b8d2e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("orders", "created_by", existing_type=sa.UUID(as_uuid=True), nullable=True)
    # A server default rather than a backfill: every existing order was a counter sale, so
    # "pos" is already true of all of them.
    op.add_column("orders", sa.Column("source", sa.String(length=20), nullable=False, server_default="pos"))
    op.add_column("orders", sa.Column("public_token", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_order_public_token", "orders", ["public_token"])


def downgrade() -> None:
    op.drop_constraint("uq_order_public_token", "orders", type_="unique")
    op.drop_column("orders", "public_token")
    op.drop_column("orders", "source")
    # Will fail if an online order exists, which is correct: a downgrade cannot invent the
    # staff user those orders never had.
    op.alter_column("orders", "created_by", existing_type=sa.UUID(as_uuid=True), nullable=False)
