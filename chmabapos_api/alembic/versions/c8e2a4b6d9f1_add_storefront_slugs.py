"""add public storefront slugs

Adds the human-readable public identity for the storefront URL
``/<company-slug>/<store-slug>``:

* ``companies.slug`` — globally unique, the first path segment.
* ``stores.slug`` — unique per company, the second path segment.
* ``previous_slugs`` on both — the slugs this row used to have, so a rename can
  still redirect a link a merchant already printed or shared.

Both columns stay nullable: a company or store without a slug keeps working
through the legacy ``/order/<token>`` link, and rows are backfilled here so
every existing tenant gets a usable URL immediately.

Revision ID: c8e2a4b6d9f1
Revises: b7d1e2f3a4c5
Create Date: 2026-10-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.slugs import (
    DEFAULT_COMPANY_SLUG,
    DEFAULT_STORE_SLUG,
    RESERVED_COMPANY_SLUGS,
    RESERVED_STORE_SLUGS,
    allocate_slug,
    slugify,
)


revision: str = 'c8e2a4b6d9f1'
down_revision: Union[str, None] = 'b7d1e2f3a4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _companies_table() -> sa.TableClause:
    return sa.table(
        'companies',
        sa.column('id', postgresql.UUID(as_uuid=True)),
        sa.column('name', sa.String),
        sa.column('slug', sa.String),
    )


def _stores_table() -> sa.TableClause:
    return sa.table(
        'stores',
        sa.column('id', postgresql.UUID(as_uuid=True)),
        sa.column('company_id', postgresql.UUID(as_uuid=True)),
        sa.column('name', sa.String),
        sa.column('slug', sa.String),
    )


def upgrade() -> None:
    op.add_column('companies', sa.Column('slug', sa.String(length=50), nullable=True))
    op.add_column('companies', sa.Column('previous_slugs', sa.JSON(), nullable=True))
    op.add_column('stores', sa.Column('slug', sa.String(length=50), nullable=True))
    op.add_column('stores', sa.Column('previous_slugs', sa.JSON(), nullable=True))

    bind = op.get_bind()
    companies = _companies_table()
    stores = _stores_table()

    # Company slugs are globally unique, so one shared pool across all tenants.
    company_slugs: set[str] = set()
    company_rows = bind.execute(
        sa.select(companies.c.id, companies.c.name).order_by(companies.c.id)
    ).all()
    for row in company_rows:
        slug = allocate_slug(
            slugify(row.name, fallback=DEFAULT_COMPANY_SLUG),
            company_slugs,
            RESERVED_COMPANY_SLUGS,
            fallback=DEFAULT_COMPANY_SLUG,
        )
        bind.execute(sa.update(companies).where(companies.c.id == row.id).values(slug=slug))

    # Store slugs only have to be unique within their company. Stores that
    # already share a name (the unique constraint is on the name) get suffixed.
    store_slugs: dict[object, set[str]] = {}
    store_rows = bind.execute(
        sa.select(stores.c.id, stores.c.company_id, stores.c.name).order_by(
            stores.c.company_id, stores.c.id
        )
    ).all()
    for row in store_rows:
        taken = store_slugs.setdefault(row.company_id, set())
        slug = allocate_slug(
            slugify(row.name, fallback=DEFAULT_STORE_SLUG),
            taken,
            RESERVED_STORE_SLUGS,
            fallback=DEFAULT_STORE_SLUG,
        )
        bind.execute(sa.update(stores).where(stores.c.id == row.id).values(slug=slug))

    # Postgres treats NULLs as distinct, so stores without a slug stay allowed.
    op.create_unique_constraint('uq_company_slug', 'companies', ['slug'])
    op.create_unique_constraint('uq_store_company_slug', 'stores', ['company_id', 'slug'])


def downgrade() -> None:
    op.drop_constraint('uq_store_company_slug', 'stores', type_='unique')
    op.drop_constraint('uq_company_slug', 'companies', type_='unique')
    op.drop_column('stores', 'previous_slugs')
    op.drop_column('stores', 'slug')
    op.drop_column('companies', 'previous_slugs')
    op.drop_column('companies', 'slug')
