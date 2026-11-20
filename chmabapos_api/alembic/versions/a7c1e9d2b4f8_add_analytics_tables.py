"""Product telemetry: sessions, partitioned events and daily rollups.

The events table is range-partitioned by ``occurred_at`` so raw retention is a
``DROP TABLE`` per month rather than a mass delete that bloats the heap. The
collector creates the next months on a worker, and this revision seeds the
partitions around the deploy date so ingestion works immediately.

Revision ID: a7c1e9d2b4f8
Revises: c8f1a2b3d4e5
Create Date: 2026-11-20
"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c1e9d2b4f8"
down_revision: Union[str, None] = "c8f1a2b3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _month(value: datetime, offset: int) -> datetime:
    index = value.month - 1 + offset
    year = value.year + index // 12
    month = index % 12 + 1
    return value.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def upgrade() -> None:
    op.create_table(
        "analytics_sessions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("anonymous_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("store_id", sa.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_route", sa.String(length=200), nullable=True),
        sa.Column("exit_route", sa.String(length=200), nullable=True),
        sa.Column("referrer_host", sa.String(length=200), nullable=True),
        sa.Column("utm_source", sa.String(length=120), nullable=True),
        sa.Column("utm_medium", sa.String(length=120), nullable=True),
        sa.Column("utm_campaign", sa.String(length=120), nullable=True),
        sa.Column("utm_content", sa.String(length=120), nullable=True),
        sa.Column("utm_term", sa.String(length=120), nullable=True),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column("platform", sa.String(length=20), nullable=True),
        sa.Column("os", sa.String(length=60), nullable=True),
        sa.Column("browser", sa.String(length=60), nullable=True),
        sa.Column("device_type", sa.String(length=20), nullable=True),
        sa.Column("locale", sa.String(length=20), nullable=True),
        sa.Column("timezone", sa.String(length=60), nullable=True),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
    )
    op.create_index("ix_analytics_sessions_user_time", "analytics_sessions", ["user_id", "started_at"])
    op.create_index("ix_analytics_sessions_company_time", "analytics_sessions", ["company_id", "started_at"])
    op.create_index("ix_analytics_sessions_anon", "analytics_sessions", ["anonymous_id"])

    op.create_table(
        "analytics_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("event_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("anonymous_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("store_id", sa.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("route", sa.String(length=200), nullable=True),
        sa.Column("route_key", sa.String(length=80), nullable=True),
        sa.Column("element_key", sa.String(length=120), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("properties", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("context", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.UniqueConstraint("event_id", "occurred_at", name="ux_analytics_events_event_id"),
        postgresql_partition_by="RANGE (occurred_at)",
    )
    op.create_index("ix_analytics_events_name_time", "analytics_events", ["name", "occurred_at"])
    op.create_index("ix_analytics_events_session", "analytics_events", ["session_id", "occurred_at"])
    op.create_index("ix_analytics_events_user_time", "analytics_events", ["user_id", "occurred_at"])
    op.create_index("ix_analytics_events_company_time", "analytics_events", ["company_id", "occurred_at"])

    # Seed the partitions around the deploy so the collector works before the
    # maintenance worker has run once. One month back covers a skewed clock;
    # three ahead covers a deploy that is not restarted for a quarter.
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for offset in range(-1, 4):
        lower = _month(start, offset)
        upper = _month(lower, 1)
        name = f"analytics_events_{lower.strftime('%Y_%m')}"
        op.execute(
            f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF analytics_events "
            f"FOR VALUES FROM ('{lower.isoformat()}') TO ('{upper.isoformat()}')"
        )

    op.create_table(
        "analytics_daily_rollups",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("name", sa.String(length=80), primary_key=True),
        sa.Column("route_key", sa.String(length=80), primary_key=True),
        sa.Column("source", sa.String(length=20), primary_key=True),
        sa.Column("company_key", sa.String(length=40), primary_key=True),
        sa.Column("events", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sessions", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("users", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("p50_ms", sa.Integer(), nullable=True),
        sa.Column("p95_ms", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("analytics_daily_rollups")
    op.drop_table("analytics_events")
    op.drop_table("analytics_sessions")
