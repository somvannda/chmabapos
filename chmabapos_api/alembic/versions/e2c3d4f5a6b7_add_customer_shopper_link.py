"""Link a merchant's customer record to the platform shopper behind it.

A guest who signs in is already merged onto their past orders, but the merchant's
own customer list had no idea that person was registered: the CRM row and the
shopper were two unrelated records for the same human. ``customers.shopper_id``
records the link, so a signed-in shopper is recognisable at the counter.

Additive and nullable: a customer with no account stays a customer with no
account. ON DELETE SET NULL, because removing a shopper must never delete the
merchant's record of them.

Revision ID: e2c3d4f5a6b7
Revises: f2b8d4a6c1e9
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2c3d4f5a6b7"
down_revision: Union[str, None] = "f2b8d4a6c1e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("shopper_id", sa.UUID(), nullable=True))
    op.create_index("ix_customers_shopper_id", "customers", ["shopper_id"])
    op.create_foreign_key(
        "fk_customers_shopper_id",
        "customers",
        "shopper_accounts",
        ["shopper_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_customers_shopper_id", "customers", type_="foreignkey")
    op.drop_index("ix_customers_shopper_id", table_name="customers")
    op.drop_column("customers", "shopper_id")
