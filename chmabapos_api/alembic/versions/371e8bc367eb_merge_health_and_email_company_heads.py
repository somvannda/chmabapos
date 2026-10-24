"""Reunite the two migration heads created by concurrent merges.

``c9e2b4a8d1f6`` (system health tables) and ``2eb98b1092b9``
(``email_sends.company_id``) both revise ``d1f3a5b7c9e2``. Their PRs were each
green against their own base, but landing both left ``main`` with two heads, and
the API job fails at "Check there is a single Alembic head" - which also blocks
every deploy, because the deploy workflow runs only after a green CI.

The two changes are independent and have already been applied on any database
that upgraded either branch, so this revision is intentionally empty: it exists
only to make the graph linear again.

Revision ID: 371e8bc367eb
Revises: c9e2b4a8d1f6, 2eb98b1092b9
Create Date: 2026-10-24
"""

from typing import Sequence, Union

revision: str = "371e8bc367eb"
down_revision: Union[str, Sequence[str], None] = ("c9e2b4a8d1f6", "2eb98b1092b9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Nothing to change: both parent revisions are already applied."""


def downgrade() -> None:
    """Splitting the heads again is never wanted, so this is a no-op."""
