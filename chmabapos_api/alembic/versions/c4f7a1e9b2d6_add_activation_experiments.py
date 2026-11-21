"""Draft activation experiments proposed by the step review.

An experiment is created only from an accepted step-review proposal, and always
starts in ``draft``: there is no traffic split until a human enables it. The row
keeps the hypothesis, the step it would change, the metric that would judge it,
the guardrails and the proposed variant, plus a pointer to the insight that
proposed it so a result can be read next to its evidence.

Revision ID: c4f7a1e9b2d6
Revises: b6e2d4f8a1c3
Create Date: 2026-11-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4f7a1e9b2d6"
down_revision: Union[str, None] = "b6e2d4f8a1c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activation_experiments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("stage_key", sa.String(length=80), nullable=False),
        sa.Column("primary_metric", sa.String(length=80), nullable=False),
        sa.Column(
            "guardrails",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "variant",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # draft | running | stopped | shipped | reverted. A new row is always draft.
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "insight_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("ai_insights.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_activation_experiments_created_at", "activation_experiments", ["created_at"])
    op.create_index("ix_activation_experiments_status", "activation_experiments", ["status"])


def downgrade() -> None:
    op.drop_table("activation_experiments")
