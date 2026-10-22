"""Snapshot purchased plan terms on subscriptions.

Existing paid subscriptions keep the terms that were in force when they were
purchased; an admin edit only affects new checkouts until the next renewal.
`capacity_checked_at` lets the billing worker enforce a newly effective period's
limits once, without sweeping every paid workspace on every run.

Revision ID: e8f9a0b1c2d3
Revises: d4f9b2c7e1a8
Create Date: 2026-10-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d4f9b2c7e1a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("plan_terms", sa.JSON(), nullable=True))
    op.add_column("subscriptions", sa.Column("capacity_checked_at", sa.DateTime(timezone=True), nullable=True))
    # Free is the live baseline and must follow the current Free plan. Paid
    # rows keep the terms they were sold under until their next checkout.
    op.execute(
        """
        UPDATE subscriptions AS s
        SET plan_terms = json_build_object(
            'code', p.code,
            'name', p.name,
            'description', p.description,
            'monthly_price', p.monthly_price,
            'max_stores', p.max_stores,
            'max_members', p.max_members,
            'transaction_limit', p.transaction_limit,
            'capabilities', COALESCE(p.capabilities, '{}'::json)
        )
        FROM plans AS p
        WHERE p.code = s.plan_code
          AND s.plan_code <> 'free'
          AND s.status IN ('active', 'pending')
          AND s.plan_terms IS NULL
        """
    )
    # Existing rows are already reconciled against the frozen snapshot; new or
    # renewed rows start unchecked so the worker enforces the new period once.
    op.execute("UPDATE subscriptions SET capacity_checked_at = now() WHERE status = 'active'")


def downgrade() -> None:
    op.drop_column("subscriptions", "capacity_checked_at")
    op.drop_column("subscriptions", "plan_terms")
