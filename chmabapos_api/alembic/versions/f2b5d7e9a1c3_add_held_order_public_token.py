"""add a public tracking token to held orders

Adds ``held_orders.public_token``: an unguessable token that lets the customer
who placed a public order follow it, without needing an account.

Deliberately separate from ``stores.public_order_token``. A store's address is
meant to be shared and printed on a QR code; an order's status is personal, and
a token that reveals one must not reveal the other. It is also not the row id:
an enumerable id in a public URL would expose other customers' orders.

Nullable, so existing tickets are unaffected and only public submissions get one.

Revision ID: f2b5d7e9a1c3
Revises: e1a4c6d8f0b2
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f2b5d7e9a1c3'
down_revision: Union[str, None] = 'e1a4c6d8f0b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('held_orders', sa.Column('public_token', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_held_order_public_token', 'held_orders', ['public_token'])


def downgrade() -> None:
    op.drop_constraint('uq_held_order_public_token', 'held_orders', type_='unique')
    op.drop_column('held_orders', 'public_token')
