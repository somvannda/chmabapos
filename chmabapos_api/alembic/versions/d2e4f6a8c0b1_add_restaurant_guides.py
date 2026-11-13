"""add the restaurant guide path

Adds the Restaurant category and its eight guides to a database that already ran
the coffee-shop seed. A fresh database gets both paths from
``a8c9e1f3b5d7`` because that migration imports the current corpus; this revision
is for deployments that already exist.

Revision ID: d2e4f6a8c0b1
Revises: b9d0f2a4c6e8
Create Date: 2026-11-13
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2e4f6a8c0b1"
down_revision: Union[str, None] = "b9d0f2a4c6e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUIDE_NAMESPACE = uuid.UUID("6f1b7f40-3c1d-4f4e-9b0a-2d7e5c8a1f33")


def _category_id(slug: str) -> uuid.UUID:
    return uuid.uuid5(GUIDE_NAMESPACE, f"category:{slug}")


def _guide_id(category: str, slug: str) -> uuid.UUID:
    return uuid.uuid5(GUIDE_NAMESPACE, f"guide:{category}:{slug}")


def upgrade() -> None:
    from app import guide_content

    category = next(item for item in guide_content.GUIDE_CATEGORIES if item["slug"] == "restaurant")
    guides = [item for item in guide_content.GUIDES if item["category"] == "restaurant"]
    now = datetime.now(timezone.utc)

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
    op.execute(
        postgresql.insert(category_table)
        .values(
            id=_category_id(category["slug"]),
            slug=category["slug"],
            name=category["name"],
            description=category["description"],
            icon=category["icon"],
            accent=category["accent"],
            position=category["position"],
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["slug"])
    )

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
    for guide in guides:
        op.execute(
            postgresql.insert(guide_table)
            .values(
                id=_guide_id(guide["category"], guide["slug"]),
                category_id=_category_id(guide["category"]),
                slug=guide["slug"],
                title=guide["title"],
                summary=guide["summary"],
                group_title=guide["group_title"],
                level=guide["level"],
                estimated_minutes=guide["estimated_minutes"],
                intro="\n\n".join(guide["intro"]),
                learning_points=guide["learning_points"],
                requirements=guide["requirements"],
                sections=guide["sections"],
                takeaways=guide["takeaways"],
                seo_title=guide.get("seo_title"),
                seo_description=guide.get("seo_description"),
                status="published",
                is_featured=guide.get("is_featured", False),
                position=guide["position"],
                view_count=0,
                published_at=now,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_guide_category_slug")
        )


def downgrade() -> None:
    from app import guide_content

    slugs = [item["slug"] for item in guide_content.GUIDES if item["category"] == "restaurant"]
    guide_table = sa.table("guides", sa.column("slug", sa.String))
    category_table = sa.table("guide_categories", sa.column("slug", sa.String))
    op.execute(guide_table.delete().where(guide_table.c.slug.in_(slugs)))
    op.execute(category_table.delete().where(category_table.c.slug == "restaurant"))
