"""drop_fixed_role_checks

Phase 1 introduced company-defined roles. The `ck_memberships_role` /
`ck_invitations_role` CHECK constraints from the hardening work only allowed the
four built-in keys, so custom roles (e.g. ``role_floor_lead``) were rejected at
the database. Role validity is now enforced per company in the API (a role must
exist for the company's roles), so drop the fixed-set checks.

Revision ID: e5a9c1d2b3f4
Revises: d4f8a1c2b3e6
Create Date: 2026-10-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e5a9c1d2b3f4'
down_revision: Union[str, None] = 'd4f8a1c2b3e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FIXED = "'owner', 'manager', 'inventory_manager', 'cashier'"


def upgrade() -> None:
    op.drop_constraint('ck_invitations_role', 'invitations', type_='check')
    op.drop_constraint('ck_memberships_role', 'memberships', type_='check')


def downgrade() -> None:
    op.create_check_constraint('ck_memberships_role', 'memberships', f"role IN ({_FIXED})")
    op.create_check_constraint('ck_invitations_role', 'invitations', f"role IN ({_FIXED})")
