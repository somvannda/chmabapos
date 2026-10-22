"""Contact consent and linked platform accounts.

Imported leads need a record of *why* they can be mailed, and a contact can be
the same person as a platform user. `consent_at`/`consent_source` record the
former, `user_id` the latter; unlinking an account never deletes the contact.

Revision ID: d4f9b2c7e1a8
Revises: b6d2f8a1c4e7
Create Date: 2026-10-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4f9b2c7e1a8"
down_revision: Union[str, None] = "b6d2f8a1c4e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("contacts", sa.Column("consent_source", sa.String(60), nullable=True))
    op.add_column("contacts", sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_contacts_user_id", "contacts", "users", ["user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_contacts_user_id", "contacts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_contacts_user_id", table_name="contacts")
    op.drop_constraint("fk_contacts_user_id", "contacts", type_="foreignkey")
    op.drop_column("contacts", "consent_at")
    op.drop_column("contacts", "consent_source")
    op.drop_column("contacts", "user_id")
