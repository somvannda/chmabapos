"""add_roles_and_permissions

Introduce company-defined roles and a permission catalog. ``Membership.role``
keeps storing the role key (a string), so existing role checks are unaffected;
this migration creates the tables and seeds the four built-in roles (and their
default permission sets) for every existing company.

Revision ID: d4f8a1c2b3e6
Revises: b8e4a2c1d3f5
Create Date: 2026-10-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.permissions import DEFAULT_ROLE_PERMISSIONS, SYSTEM_ROLE_NAMES, SYSTEM_ROLES


revision: str = 'd4f8a1c2b3e6'
down_revision: Union[str, None] = 'b8e4a2c1d3f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(length=60), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('is_system', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'key', name='uq_role_company_key'),
        sa.UniqueConstraint('company_id', 'name', name='uq_role_company_name'),
    )
    op.create_index('ix_roles_company_id', 'roles', ['company_id'])
    op.create_table(
        'role_permissions',
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('permission', sa.String(length=60), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'permission'),
    )

    conn = op.get_bind()
    company_ids = conn.execute(sa.text('SELECT id FROM companies')).scalars().all()
    for company_id in company_ids:
        for key in SYSTEM_ROLES:
            role_id = conn.execute(
                sa.text(
                    'INSERT INTO roles (id, company_id, key, name, is_system, created_at) '
                    'VALUES (gen_random_uuid(), :company_id, :key, :name, true, now()) RETURNING id'
                ),
                {'company_id': company_id, 'key': key, 'name': SYSTEM_ROLE_NAMES[key]},
            ).scalar_one()
            for permission in DEFAULT_ROLE_PERMISSIONS[key]:
                conn.execute(
                    sa.text('INSERT INTO role_permissions (role_id, permission) VALUES (:role_id, :permission)'),
                    {'role_id': role_id, 'permission': permission},
                )


def downgrade() -> None:
    op.drop_table('role_permissions')
    op.drop_index('ix_roles_company_id', table_name='roles')
    op.drop_table('roles')
