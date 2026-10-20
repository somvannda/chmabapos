"""Show what a plan checkout is expected to cover.

The payment modal could say "Starter plan - $0.99" but not *when* the paid time
starts and ends, so an early renewal and an upgrade looked identical. Record the
projected window at checkout (display-only) so the modal can state "Covers <from>
- <until>". The immutable ``period_start``/``period_end`` are still set at
fulfilment, when the real boundary is known.

Revision ID: f2a4c6e8b0d1
Revises: b8e2f4a6c0d3
Create Date: 2026-10-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a4c6e8b0d1"
down_revision: Union[str, None] = "b8e2f4a6c0d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("billing_payments", sa.Column("covers_from", sa.DateTime(timezone=True), nullable=True))
    op.add_column("billing_payments", sa.Column("covers_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("billing_payments", "covers_until")
    op.drop_column("billing_payments", "covers_from")
