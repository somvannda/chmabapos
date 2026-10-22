"""Let drip steps target contacts as well as platform users.

`mailing_drip_deliveries` becomes a polymorphic ledger: a row points at either
`user_id` or `contact_id`, never both. The unique guards stay per recipient kind
so a retried run cannot email the same person the same step twice.

Revision ID: f2b6d4a8c1e9
Revises: e8f9a0b1c2d3
Create Date: 2026-10-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2b6d4a8c1e9"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("mailing_drip_deliveries", "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("mailing_drip_deliveries", sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_mailing_drip_deliveries_contact_id",
        "mailing_drip_deliveries",
        "contacts",
        ["contact_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_mailing_drip_deliveries_contact_id", "mailing_drip_deliveries", ["contact_id"])
    op.create_unique_constraint(
        "uq_mailing_drip_contact_step",
        "mailing_drip_deliveries",
        ["contact_id", "step_id"],
    )
    op.create_check_constraint(
        "ck_mailing_drip_one_recipient",
        "mailing_drip_deliveries",
        "(user_id IS NOT NULL) <> (contact_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_mailing_drip_one_recipient", "mailing_drip_deliveries", type_="check")
    op.drop_constraint("uq_mailing_drip_contact_step", "mailing_drip_deliveries", type_="unique")
    op.drop_index("ix_mailing_drip_deliveries_contact_id", table_name="mailing_drip_deliveries")
    op.drop_constraint("fk_mailing_drip_deliveries_contact_id", "mailing_drip_deliveries", type_="foreignkey")
    # Contact rows cannot exist in the user-only ledger this downgrades to.
    op.execute("DELETE FROM mailing_drip_deliveries WHERE contact_id IS NOT NULL")
    op.drop_column("mailing_drip_deliveries", "contact_id")
    op.alter_column("mailing_drip_deliveries", "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
