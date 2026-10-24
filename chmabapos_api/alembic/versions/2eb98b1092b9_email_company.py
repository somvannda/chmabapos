"""Scope queued billing notices to their workspace.

Paying one workspace must not cancel another workspace's queued reminder when the
same owner belongs to both. Existing rows stay NULL and are cleaned up only by
the legacy recipient fallback.

Revision ID: 2eb98b1092b9
Revises: d1f3a5b7c9e2
Create Date: 2026-10-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2eb98b1092b9"
down_revision: Union[str, None] = "d1f3a5b7c9e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("email_sends", sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_email_sends_company_id", "email_sends", "companies", ["company_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_email_send_company", "email_sends", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_email_send_company", table_name="email_sends")
    op.drop_constraint("fk_email_sends_company_id", "email_sends", type_="foreignkey")
    op.drop_column("email_sends", "company_id")
