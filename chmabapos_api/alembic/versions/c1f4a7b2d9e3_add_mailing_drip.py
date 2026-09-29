"""add_mailing_drip

Automated drip: a delivery ledger so each (user, step) pair is emailed at most
once, plus a ``source`` marker on ``email_sends`` to tell manual sends from
automated ones in the delivery log.

Revision ID: c1f4a7b2d9e3
Revises: b8e2d4f6a1c3
Create Date: 2026-09-29 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1f4a7b2d9e3'
down_revision: Union[str, None] = 'b8e2d4f6a1c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('email_sends', sa.Column('source', sa.String(length=20), nullable=False, server_default='manual'))

    op.create_table(
        'mailing_drip_deliveries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('step_id', sa.String(length=60), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'step_id', name='uq_mailing_drip_user_step'),
    )
    op.create_index('ix_mailing_drip_deliveries_user_id', 'mailing_drip_deliveries', ['user_id'], unique=False)
    op.create_index('ix_mailing_drip_step', 'mailing_drip_deliveries', ['step_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_mailing_drip_step', table_name='mailing_drip_deliveries')
    op.drop_index('ix_mailing_drip_deliveries_user_id', table_name='mailing_drip_deliveries')
    op.drop_table('mailing_drip_deliveries')
    op.drop_column('email_sends', 'source')
