"""Merge the order-rate and delivery-help migrations.

Two independent branches forked from ``f9a1c3e5b7d2``:

* ``c8d2f5a1e9b4`` -> ``d6e3a1b8c4f2`` (delivery help article)
* ``e7d9c1b3a5f2`` (freeze each order's company base rate)

Both were merged to main separately, leaving two heads. Nothing depends on
their order, so a merge revision reunites them and keeps
``alembic upgrade head`` valid.

Revision ID: a3f5c7e9b1d2
Revises: d6e3a1b8c4f2, e7d9c1b3a5f2
Create Date: 2026-10-20
"""

from typing import Sequence, Union

revision: str = "a3f5c7e9b1d2"
down_revision: Union[str, Sequence[str], None] = ("d6e3a1b8c4f2", "e7d9c1b3a5f2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
