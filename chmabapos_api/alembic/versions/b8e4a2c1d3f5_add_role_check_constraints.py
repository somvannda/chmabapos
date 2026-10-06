"""add_role_check_constraints

Role values were only validated at the API boundary (Pydantic), so a bad
out-of-band write (raw SQL, tooling, a future code path) could store a role
string that matches no guard. Add database-level CHECK constraints for the
tenant and platform role columns, and give the two tenant role columns a server
default so raw inserts do not have to supply one.

Revision ID: b8e4a2c1d3f5
Revises: a7d3f1c9b2e4
Create Date: 2026-10-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8e4a2c1d3f5'
down_revision: Union[str, None] = 'a7d3f1c9b2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_ROLES = "'owner', 'manager', 'inventory_manager', 'cashier'"


def upgrade() -> None:
    op.create_check_constraint(
        'ck_users_platform_role',
        'users',
        "platform_role IS NULL OR platform_role IN ('admin', 'super_admin')",
    )
    op.create_check_constraint('ck_memberships_role', 'memberships', f"role IN ({TENANT_ROLES})")
    op.create_check_constraint('ck_invitations_role', 'invitations', f"role IN ({TENANT_ROLES})")
    op.alter_column('memberships', 'role', existing_type=sa.String(length=40), server_default='cashier')
    op.alter_column('invitations', 'role', existing_type=sa.String(length=40), server_default='cashier')


def downgrade() -> None:
    op.alter_column('invitations', 'role', existing_type=sa.String(length=40), server_default=None)
    op.alter_column('memberships', 'role', existing_type=sa.String(length=40), server_default=None)
    op.drop_constraint('ck_invitations_role', 'invitations', type_='check')
    op.drop_constraint('ck_memberships_role', 'memberships', type_='check')
    op.drop_constraint('ck_users_platform_role', 'users', type_='check')
