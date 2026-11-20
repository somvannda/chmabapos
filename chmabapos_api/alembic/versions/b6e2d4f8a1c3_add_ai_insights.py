"""AI insight layer: cited digests and the run log behind them.

``ai_insights`` stores one reviewed artifact (a friction digest today) with the
evidence it cited and the validator's verdict. ``ai_runs`` is the cost and
debugging trail: one row per provider call, so a repaired or failed attempt is
visible after the fact instead of being folded into the insight.

Revision ID: b6e2d4f8a1c3
Revises: a7c1e9d2b4f8
Create Date: 2026-11-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b6e2d4f8a1c3"
down_revision: Union[str, None] = "a7c1e9d2b4f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_insights",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("stage_key", sa.String(length=80), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("prompt_version", sa.String(length=60), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        # passed: the first reply validated. repaired: the retry did.
        # fallback: deterministic rules, because the provider failed or lied.
        # insufficient: too little data to ask a provider at all.
        sa.Column("validator", sa.String(length=20), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=True),
        sa.Column("decided_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_ai_insights_created_at", "ai_insights", ["created_at"])
    op.create_index("ix_ai_insights_kind", "ai_insights", ["kind"])

    op.create_table(
        "ai_runs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("insight_id", sa.UUID(as_uuid=True), sa.ForeignKey("ai_insights.id", ondelete="SET NULL"), nullable=True),
        sa.Column("prompt_version", sa.String(length=60), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        # ok | parse_error | provider_error | fallback
        sa.Column("outcome", sa.String(length=30), nullable=False),
    )
    op.create_index("ix_ai_runs_created_at", "ai_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("ai_runs")
    op.drop_table("ai_insights")
