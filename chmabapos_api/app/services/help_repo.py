"""Read the DB-backed help corpus, falling back to the static seed module.

Phase 1 of the admin help editor (``docs/help-editor-plan.md``). The
``help_articles`` table is the source of truth for the help center; it is seeded
from ``app/support_content.py``. If the table is empty (or the migration has not
run), callers fall back to the static corpus so help never breaks.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HelpArticle

# Kept for API parity with support_content's section shape. DB rows carry their
# Khmer text inline via the ``*_km`` fields.
ARTICLE_FIELDS = ("title", "steps", "tip", "verticals", "roles")


async def load_sections(db: AsyncSession) -> list[dict[str, Any]] | None:
    """Return active articles grouped into sections, or ``None`` when empty.

    ``None`` signals the caller to use the static fallback corpus. Sections are
    ordered by their first article's ``position`` so the authored order is kept.
    """
    rows = (
        await db.execute(
            select(HelpArticle)
            .where(HelpArticle.is_active.is_(True))
            .order_by(HelpArticle.position, HelpArticle.id)
        )
    ).scalars().all()
    if not rows:
        return None

    sections: dict[str, dict[str, Any]] = {}
    for row in rows:
        section = sections.get(row.section_id)
        if section is None:
            section = {
                "id": row.section_id,
                "title": row.section_title,
                "title_km": row.section_title_km,
                "blurb": row.section_blurb,
                "blurb_km": row.section_blurb_km,
                "articles": [],
            }
            sections[row.section_id] = section
        section["articles"].append(
            {
                "id": row.id,
                "title": row.title,
                "title_km": row.title_km,
                "steps": row.steps,
                "steps_km": row.steps_km,
                "tip": row.tip,
                "tip_km": row.tip_km,
                "verticals": row.verticals,
                "roles": row.roles,
            }
        )
    return list(sections.values())
