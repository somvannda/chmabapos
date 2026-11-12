"""refresh the seeded coffee guide copy

The first release described a size-picker modal and several modifier groups per
product. The shipped register shows each size as a tile and attaches one
modifier group to a product, so the text sent merchants looking for controls
that do not exist. This revision copies the corrected copy from
``app/guide_content.py`` into the seeded rows. Admin edits made after this
revision are preserved; running it again is harmless because it only touches
the known seed slugs.

Revision ID: b9d0f2a4c6e8
Revises: a8c9e1f3b5d7
Create Date: 2026-11-12
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b9d0f2a4c6e8"
down_revision: Union[str, None] = "a8c9e1f3b5d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app import guide_content

    for guide in guide_content.GUIDES:
        op.execute(
            sa.text(
                """
                UPDATE guides
                   SET title = :title,
                       summary = :summary,
                       group_title = :group_title,
                       level = :level,
                       estimated_minutes = :estimated_minutes,
                       intro = :intro,
                       learning_points = CAST(:learning_points AS json),
                       requirements = CAST(:requirements AS json),
                       sections = CAST(:sections AS json),
                       takeaways = CAST(:takeaways AS json),
                       seo_title = :seo_title,
                       seo_description = :seo_description,
                       updated_at = now()
                 WHERE slug = :slug
                """
            ).bindparams(
                title=guide["title"],
                summary=guide["summary"],
                group_title=guide["group_title"],
                level=guide["level"],
                estimated_minutes=guide["estimated_minutes"],
                intro="\n\n".join(guide["intro"]),
                learning_points=json.dumps(guide["learning_points"]),
                requirements=json.dumps(guide["requirements"]),
                sections=json.dumps(guide["sections"]),
                takeaways=json.dumps(guide["takeaways"]),
                seo_title=guide.get("seo_title"),
                seo_description=guide.get("seo_description"),
                slug=guide["slug"],
            )
        )


def downgrade() -> None:
    # Copy fixes are not destructive; there is no previous wording to restore.
    pass
