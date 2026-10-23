"""Store the URL a recipient clicked.

Resend's `email.clicked` event carries the tracked link, which the delivery log
and contact history can show instead of only a timestamp.

Revision ID: b8d3f1a6c9e2
Revises: a7c1e9d3b5f2
Create Date: 2026-10-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8d3f1a6c9e2"
down_revision: Union[str, None] = "a7c1e9d3b5f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("email_sends", sa.Column("clicked_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("email_sends", "clicked_url")
