"""grant_deliveries_manage

Give the new ``deliveries.manage`` permission to the built-in roles that
already reach the delivery board. New companies are seeded from
``DEFAULT_ROLE_PERMISSIONS``; this backfills the roles that predate the key.

Revision ID: c8d2f5a1e9b4
Revises: f9a1c3e5b7d2
Create Date: 2026-10-20 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c8d2f5a1e9b4'
down_revision: Union[str, None] = 'f9a1c3e5b7d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission)
        SELECT id, 'deliveries.manage'
        FROM roles
        WHERE is_system = true AND key IN ('owner', 'manager', 'cashier')
        ON CONFLICT (role_id, permission) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission = 'deliveries.manage'")
