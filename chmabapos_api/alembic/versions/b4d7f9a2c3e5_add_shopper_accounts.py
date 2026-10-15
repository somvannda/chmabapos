"""add shopper accounts

Shopper (customer) accounts, kept entirely separate from staff ``users``.

That separation is the point. The staff ``User`` table drives memberships, plan
seat counts, invitations and the platform-admin user list; putting customers in it
would inflate plan usage and confuse staff administration. A shopper is a
platform-level identity that can buy from any store on Chmaba.

Multi-provider from the outset. ``google_sub`` and ``telegram_id`` are columns
now, not later: the decision was that Telegram ships alongside email and Google,
and adding a provider to an existing identity model should be a code change, not
a migration.

Sign-in is passwordless - a six-digit emailed code - so there is nothing here to
hash a password into, and nothing for a customer to reuse or leak.

Revision ID: b4d7f9a2c3e5
Revises: f2b5d7e9a1c3
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b4d7f9a2c3e5'
down_revision: Union[str, None] = 'f2b5d7e9a1c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'shopper_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('full_name', sa.String(length=160), nullable=True),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('google_sub', sa.String(length=255), nullable=True),
        sa.Column('telegram_id', sa.String(length=64), nullable=True),
        sa.Column('is_email_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_shopper_accounts_email', 'shopper_accounts', ['email'], unique=True)
    op.create_unique_constraint('uq_shopper_google_sub', 'shopper_accounts', ['google_sub'])
    op.create_unique_constraint('uq_shopper_telegram_id', 'shopper_accounts', ['telegram_id'])

    op.create_table(
        'shopper_email_codes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'shopper_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('shopper_accounts.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        # Only the hash is stored, never the code: a database read must not be
        # enough to sign in as somebody.
        sa.Column('token_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('shopper_email_codes')
    op.drop_constraint('uq_shopper_telegram_id', 'shopper_accounts', type_='unique')
    op.drop_constraint('uq_shopper_google_sub', 'shopper_accounts', type_='unique')
    op.drop_index('ix_shopper_accounts_email', table_name='shopper_accounts')
    op.drop_table('shopper_accounts')
