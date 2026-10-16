"""Add a contact email to stores.

The store already carried a phone, entered once and used for receipts, and the storefront
badge shows it. Email only existed on the company, so a shop could not publish one per
location - and the public store page had nothing to show in its place.

Revision ID: f7c1a4b8d2e6
Revises: e7a1c3d5f6b8
Create Date: 2026-10-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7c1a4b8d2e6"
down_revision: Union[str, None] = "e7a1c3d5f6b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: existing stores simply have no public contact address, and the storefront
    # omits the line rather than showing an empty one.
    op.add_column("stores", sa.Column("email", sa.String(length=180), nullable=True))


def downgrade() -> None:
    op.drop_column("stores", "email")
