"""add the directory listing flag

Adds ``stores.listed_in_directory``: the explicit opt-in that decides whether a
store appears in the public directory, rather than inferring it from having
online ordering switched on.

Existing rows are backfilled to **true** where the store would already have been
listed (active, online ordering enabled, inside an active company, and with both
slugs present). Those merchants had already effectively opted in by publishing an
orderable page, so backfilling true keeps the directory from emptying itself on
deploy; from this revision on, listing is an explicit choice.

Revision ID: e1a4c6d8f0b2
Revises: d9f3b5c7e1a2
Create Date: 2026-10-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1a4c6d8f0b2'
down_revision: Union[str, None] = 'd9f3b5c7e1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'stores',
        sa.Column('listed_in_directory', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    # Backfill: whatever the directory would have shown before this revision keeps
    # showing, so introducing the flag is not a silent un-listing of live stores.
    op.execute(
        """
        UPDATE stores
           SET listed_in_directory = true
         WHERE public_order_enabled = true
           AND is_active = true
           AND slug IS NOT NULL
           AND company_id IN (SELECT id FROM companies WHERE is_active = true AND slug IS NOT NULL)
        """
    )


def downgrade() -> None:
    op.drop_column('stores', 'listed_in_directory')
