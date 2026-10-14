"""add storefront branding settings

Adds ``stores.storefront``: the branding and policy bag that turns a store page
into the merchant's own shop -- tagline, accent preset, logo, cover, banner,
opening hours, socials, policies.

It is a JSON column rather than a table because it is a single, small,
whole-thing-read/whole-thing-written document with no queryable structure: the
public storefront reads it in one go and the editor writes it in one go. Accent
values are preset keys, never raw colours, so a merchant cannot publish an
unreadable page (see ``app/storefront.py``).

Revision ID: d9f3b5c7e1a2
Revises: c8e2a4b6d9f1
Create Date: 2026-10-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9f3b5c7e1a2'
down_revision: Union[str, None] = 'c8e2a4b6d9f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable with no backfill: an absent bag means "no branding configured",
    # which the public page renders as sensible defaults.
    op.add_column('stores', sa.Column('storefront', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('stores', 'storefront')
