"""starter_include_table_management

Starter regains table & restaurant mode (O1). The gate reads
``Plan.capabilities`` from the database, so update the seeded Starter row; new
databases pick this up from ``DEFAULT_FEATURES_BY_PLAN`` at seed time.

Revision ID: c7a1b2c3d4e5
Revises: b4a3c2d1e0f9
Create Date: 2026-10-03 00:00:00.000000
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7a1b2c3d4e5'
down_revision: Union[str, None] = 'b4a3c2d1e0f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _set_starter_table_management(enabled: bool) -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT code, capabilities FROM plans WHERE code = 'starter'")).fetchall()
    for code, capabilities in rows:
        caps = dict(capabilities or {})
        caps["table_management"] = enabled
        bind.execute(
            sa.text("UPDATE plans SET capabilities = CAST(:caps AS json) WHERE code = :code"),
            {"caps": json.dumps(caps), "code": code},
        )


def upgrade() -> None:
    _set_starter_table_management(True)


def downgrade() -> None:
    _set_starter_table_management(False)
