"""link an acknowledgement email to its order

Adds ``email_sends.held_order_id``, set only for the online-order acknowledgement.

This exists so a later sign-in can attach a customer's earlier **guest** orders
without storing their address a second time. The address already lives here, on
the acknowledgement row, and the order itself deliberately does not keep it - so
matching through this link respects the plan's stance on retaining as little PII
as possible rather than duplicating it into ``held_orders``.

Nullable, because the outbox carries every other kind of mail too. ``SET NULL`` on
delete: losing an order must not delete the delivery log, and losing a log row
must not touch the order.

Revision ID: e7a1c3d5f6b8
Revises: d6f9b2c4e5a7
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e7a1c3d5f6b8'
down_revision: Union[str, None] = 'd6f9b2c4e5a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('email_sends', sa.Column('held_order_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_email_send_held_order',
        'email_sends',
        'held_orders',
        ['held_order_id'],
        ['id'],
        ondelete='SET NULL',
    )
    # The merge looks orders up by recipient, so match the index the recipient
    # column already has and keep this one narrow.
    op.create_index('ix_email_send_held_order', 'email_sends', ['held_order_id'])


def downgrade() -> None:
    op.drop_index('ix_email_send_held_order', table_name='email_sends')
    op.drop_constraint('fk_email_send_held_order', 'email_sends', type_='foreignkey')
    op.drop_column('email_sends', 'held_order_id')
