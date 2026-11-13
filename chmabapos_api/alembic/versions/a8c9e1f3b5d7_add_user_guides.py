"""add the public user-guides library

Creates ``guide_categories`` and ``guides`` and seeds the first category, Coffee
shop, from ``app/guide_content.py``. The seed is the same corpus an editor sees
in the admin panel, so a fresh database already has a complete launch series
rather than an empty library.

Revision ID: a8c9e1f3b5d7
Revises: c7f2e9a4d1b8
Create Date: 2026-11-12
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a8c9e1f3b5d7"
down_revision: Union[str, None] = "c7f2e9a4d1b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Stable ids keep the seed reproducible: re-running the migration in a test
# database links the same guide to the same public URL.
GUIDE_NAMESPACE = uuid.UUID("6f1b7f40-3c1d-4f4e-9b0a-2d7e5c8a1f33")


def _category_id(slug: str) -> uuid.UUID:
    return uuid.uuid5(GUIDE_NAMESPACE, f"category:{slug}")


def _guide_id(category: str, slug: str) -> uuid.UUID:
    return uuid.uuid5(GUIDE_NAMESPACE, f"guide:{category}:{slug}")


def upgrade() -> None:
    op.create_table(
        "guide_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("icon", sa.String(length=40), nullable=False, server_default="Coffee"),
        sa.Column("accent", sa.String(length=20), nullable=False, server_default="#b46b3e"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_guide_categories_slug", "guide_categories", ["slug"], unique=True)
    op.create_index("ix_guide_categories_position", "guide_categories", ["position"])

    op.create_table(
        "guides",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("group_title", sa.String(length=80), nullable=False, server_default="Start here"),
        sa.Column("level", sa.String(length=20), nullable=False, server_default="beginner"),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("hero_image_url", sa.String(length=500), nullable=True),
        sa.Column("intro", sa.Text(), nullable=False, server_default=""),
        sa.Column("learning_points", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("requirements", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("sections", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("takeaways", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("seo_title", sa.String(length=200), nullable=True),
        sa.Column("seo_description", sa.String(length=320), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["guide_categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_id", "slug", name="uq_guide_category_slug"),
    )
    op.create_index("ix_guides_category_id", "guides", ["category_id"])
    op.create_index("ix_guides_category_position", "guides", ["category_id", "position"])
    op.create_index("ix_guides_status", "guides", ["status"])

    from app import guide_content

    category_table = sa.table(
        "guide_categories",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("icon", sa.String),
        sa.column("accent", sa.String),
        sa.column("position", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    category_rows = [
        {
            "id": _category_id(category["slug"]),
            "slug": category["slug"],
            "name": category["name"],
            "description": category["description"],
            "icon": category["icon"],
            "accent": category["accent"],
            "position": category["position"],
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        for category in guide_content.GUIDE_CATEGORIES
    ]
    if category_rows:
        op.bulk_insert(category_table, category_rows)

    guide_table = sa.table(
        "guides",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("category_id", postgresql.UUID(as_uuid=True)),
        sa.column("slug", sa.String),
        sa.column("title", sa.String),
        sa.column("summary", sa.String),
        sa.column("group_title", sa.String),
        sa.column("level", sa.String),
        sa.column("estimated_minutes", sa.Integer),
        sa.column("hero_image_url", sa.String),
        sa.column("intro", sa.Text),
        sa.column("learning_points", sa.JSON),
        sa.column("requirements", sa.JSON),
        sa.column("sections", sa.JSON),
        sa.column("takeaways", sa.JSON),
        sa.column("seo_title", sa.String),
        sa.column("seo_description", sa.String),
        sa.column("status", sa.String),
        sa.column("is_featured", sa.Boolean),
        sa.column("position", sa.Integer),
        sa.column("view_count", sa.Integer),
        sa.column("published_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    guide_rows = [
        {
            "id": _guide_id(guide["category"], guide["slug"]),
            "category_id": _category_id(guide["category"]),
            "slug": guide["slug"],
            "title": guide["title"],
            "summary": guide["summary"],
            "group_title": guide["group_title"],
            "level": guide["level"],
            "estimated_minutes": guide["estimated_minutes"],
            "hero_image_url": guide.get("hero_image_url"),
            "intro": "\n\n".join(guide["intro"]),
            "learning_points": guide["learning_points"],
            "requirements": guide["requirements"],
            "sections": guide["sections"],
            "takeaways": guide["takeaways"],
            "seo_title": guide.get("seo_title"),
            "seo_description": guide.get("seo_description"),
            "status": "published",
            "is_featured": guide.get("is_featured", False),
            "position": guide["position"],
            "view_count": 0,
            "published_at": now,
            "created_at": now,
            "updated_at": now,
        }
        for guide in guide_content.GUIDES
    ]
    if guide_rows:
        op.bulk_insert(guide_table, guide_rows)


def downgrade() -> None:
    op.drop_index("ix_guides_status", table_name="guides")
    op.drop_index("ix_guides_category_position", table_name="guides")
    op.drop_index("ix_guides_category_id", table_name="guides")
    op.drop_table("guides")
    op.drop_index("ix_guide_categories_position", table_name="guide_categories")
    op.drop_index("ix_guide_categories_slug", table_name="guide_categories")
    op.drop_table("guide_categories")
