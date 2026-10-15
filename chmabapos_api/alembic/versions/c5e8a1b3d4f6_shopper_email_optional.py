"""make the shopper email optional

Telegram sign-in supplies **no email address**: the Login Widget returns a user id,
a display name and an optional username, nothing more. So an email cannot be
required for a shopper to exist.

Keeping the column nullable is the honest representation, rather than inventing a
placeholder address like ``tg-<id>@invalid`` - a fabricated email would sit in the
same column as real ones, and every later query would have to know to exclude it.

Postgres treats NULLs as distinct in a unique index, so ``email`` stays unique for
real addresses while many provider-only shoppers coexist.

Revision ID: c5e8a1b3d4f6
Revises: b4d7f9a2c3e5
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5e8a1b3d4f6'
down_revision: Union[str, None] = 'b4d7f9a2c3e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'shopper_accounts',
        'email',
        existing_type=sa.String(length=320),
        nullable=True,
    )


def downgrade() -> None:
    # Only safe while no provider-only shoppers exist, which is why this raises
    # rather than silently failing later: a downgrade would otherwise have to
    # invent addresses for rows that never had one.
    op.alter_column(
        'shopper_accounts',
        'email',
        existing_type=sa.String(length=320),
        nullable=False,
    )
