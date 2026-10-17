"""Link a held ticket to the order it belongs to.

A public order creates two records: the order that reporting reads, and the held ticket the
kitchen works from. Nothing said which ticket belonged to which order, so the code that kept
them in step matched on the payment provider's external id - an inference that happens to
work while an order has exactly one payment, and quietly stops working the moment it has two
(a split, a retried QR, a deposit with a balance later).

An explicit link makes the relationship a fact. It is also what lets the ticket stop being
created for storefront orders later without losing the kitchen's docket: the docket and the
sale would simply point at each other.

Revision ID: e3b7c9d1f5a2
Revises: a8f4c2e6b9d3
Create Date: 2026-10-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3b7c9d1f5a2"
down_revision: Union[str, None] = "a8f4c2e6b9d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable because the tickets a cashier parks at the till belong to no order at all.
    op.add_column("held_orders", sa.Column("order_id", sa.UUID(as_uuid=True), nullable=True))
    # SET NULL rather than CASCADE: deleting an order must never delete a ticket the kitchen
    # is mid-way through, and a ticket with no order is an ordinary parked cart.
    op.create_foreign_key("fk_held_orders_order_id", "held_orders", "orders", ["order_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_held_orders_order_id", "held_orders", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_held_orders_order_id", table_name="held_orders")
    op.drop_constraint("fk_held_orders_order_id", "held_orders", type_="foreignkey")
    op.drop_column("held_orders", "order_id")
