"""attribute public orders to a signed-in shopper

Adds ``held_orders.shopper_id``: when a public order is submitted by a signed-in
shopper, the ticket is linked to their account. That link is what makes an order
history possible - without it a signed-in shopper and a guest look identical to
the database, and there is nothing to show them afterwards.

Nullable, because guest checkout remains the default and most orders will have no
shopper at all. ``SET NULL`` rather than ``CASCADE``: deleting a shopper account
must never delete a merchant's order history.

Deliberately not reusing ``created_by``, which is a foreign key to staff ``users``
and NULL for every public order. Pointing customers at the staff table is the
thing this whole identity split exists to avoid.

Revision ID: d6f9b2c4e5a7
Revises: c5e8a1b3d4f6
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd6f9b2c4e5a7'
down_revision: Union[str, None] = 'c5e8a1b3d4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('held_orders', sa.Column('shopper_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_held_order_shopper',
        'held_orders',
        'shopper_accounts',
        ['shopper_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_held_order_shopper', 'held_orders', ['shopper_id'])


def downgrade() -> None:
    op.drop_index('ix_held_order_shopper', table_name='held_orders')
    op.drop_constraint('fk_held_order_shopper', 'held_orders', type_='foreignkey')
    op.drop_column('held_orders', 'shopper_id')
