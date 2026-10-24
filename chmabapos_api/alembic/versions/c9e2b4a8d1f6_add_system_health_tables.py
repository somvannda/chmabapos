"""add system health tables

Platform self-monitoring: one row per dependency for the current state, plus an
append-only log of transitions. Nothing existing changes, so a downgrade simply
drops the two tables.

Revision ID: c9e2b4a8d1f6
Revises: d1f3a5b7c9e2
Create Date: 2026-10-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9e2b4a8d1f6"
down_revision: Union[str, None] = "d1f3a5b7c9e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_health_checks",
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False, server_default="platform"),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="warning"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("alert_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_index("ix_system_health_checks_status", "system_health_checks", ["status"])

    op.create_table(
        "system_health_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("check_name", sa.String(length=60), nullable=False),
        sa.Column("previous_status", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_health_events_check_name", "system_health_events", ["check_name"])
    op.create_index("ix_system_health_events_created", "system_health_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_system_health_events_created", table_name="system_health_events")
    op.drop_index("ix_system_health_events_check_name", table_name="system_health_events")
    op.drop_table("system_health_events")
    op.drop_index("ix_system_health_checks_status", table_name="system_health_checks")
    op.drop_table("system_health_checks")
