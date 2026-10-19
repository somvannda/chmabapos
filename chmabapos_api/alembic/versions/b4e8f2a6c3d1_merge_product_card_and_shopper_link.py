"""Merge the product-card and shopper-link migrations.

Two branches forked from f2b8d4a6c1e9: the chat product card column and the
shopper-to-customer link. Neither depends on the other, so a merge revision
reunites them and keeps ``alembic upgrade head`` valid -- without it the API
container refuses to start, because `upgrade head` cannot choose between heads.

Revision ID: b4e8f2a6c3d1
Revises: a3c9e1f5b7d2, e2c3d4f5a6b7
Create Date: 2026-10-19
"""

from typing import Sequence, Union

revision: str = "b4e8f2a6c3d1"
down_revision: Union[str, Sequence[str], None] = ("a3c9e1f5b7d2", "e2c3d4f5a6b7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
