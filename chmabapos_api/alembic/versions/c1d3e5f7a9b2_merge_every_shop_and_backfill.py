"""reunite the every-shop and assistant-backfill migration heads

``b6c8d0e2f4a6`` (the shared Every shop guide group) and ``b7e2f4a8c1d6`` (the
assistant-history backfill) were created on parallel branches from the same
parent, ``a5b7c9d1e3f5``. Neither changes the other's tables, so this merge
revision only records that both must be applied before the graph continues.

Without it a fresh database has two heads: ``alembic upgrade head`` refuses to
run, which is how the CI head check fails and a deploy would leave the API
unable to migrate.

Revision ID: c1d3e5f7a9b2
Revises: b6c8d0e2f4a6, b7e2f4a8c1d6
Create Date: 2026-11-13
"""
from typing import Sequence, Union

revision: str = "c1d3e5f7a9b2"
down_revision: Union[str, Sequence[str], None] = ("b6c8d0e2f4a6", "b7e2f4a8c1d6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
