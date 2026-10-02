"""repair held order table_id/status columns

Revision ID: f3c9d1e7a2b4
Revises: c3e4f5a6b7d8
Create Date: 2026-10-02 00:00:00.000000

Some databases report the head revision while still missing the ``table_id``
and ``status`` columns that migration ``f1a2b3c4d5e6`` adds to ``held_orders``
(the recorded alembic version drifted ahead of the real schema, so the startup
``alembic upgrade head`` was a no-op and the held-orders endpoints 500'd).
Re-add them idempotently: healthy databases are unaffected, drifted ones are
repaired.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f3c9d1e7a2b4'
down_revision: Union[str, None] = 'c3e4f5a6b7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE held_orders ADD COLUMN IF NOT EXISTS table_id UUID")
    op.execute("ALTER TABLE held_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'open'")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_held_orders_table_id') THEN
                ALTER TABLE held_orders
                    ADD CONSTRAINT fk_held_orders_table_id
                    FOREIGN KEY (table_id) REFERENCES dining_tables(id) ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE held_orders DROP CONSTRAINT IF EXISTS fk_held_orders_table_id")
    op.execute("ALTER TABLE held_orders DROP COLUMN IF EXISTS status")
    op.execute("ALTER TABLE held_orders DROP COLUMN IF EXISTS table_id")
