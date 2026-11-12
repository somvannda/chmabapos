"""Read and serialise public User Guides.

The public library and the admin editor read the same two tables. Keeping the
row-to-payload mapping here means the guide a reader sees and the guide an admin
edits can never drift into different shapes.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Guide, GuideCategory


def category_card(category: GuideCategory, guide_count: int = 0) -> dict[str, Any]:
    return {
        "id": category.id,
        "slug": category.slug,
        "name": category.name,
        "description": category.description,
        "icon": category.icon,
        "accent": category.accent,
        "position": category.position,
        "guide_count": guide_count,
    }


def guide_card(guide: Guide, category: GuideCategory) -> dict[str, Any]:
    return {
        "id": guide.id,
        "slug": guide.slug,
        "title": guide.title,
        "summary": guide.summary,
        "group_title": guide.group_title,
        "level": guide.level,
        "estimated_minutes": guide.estimated_minutes,
        "hero_image_url": guide.hero_image_url,
        "is_featured": guide.is_featured,
        "position": guide.position,
        "published_at": guide.published_at,
        "step_count": len(guide.sections or []),
        "category_slug": category.slug,
        "category_name": category.name,
        "category_accent": category.accent,
    }


def guide_detail(
    guide: Guide,
    category: GuideCategory,
    *,
    previous: dict[str, Any] | None = None,
    next_: dict[str, Any] | None = None,
    series: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        **guide_card(guide, category),
        "intro": guide.intro,
        "learning_points": guide.learning_points,
        "requirements": guide.requirements,
        "sections": guide.sections,
        "takeaways": guide.takeaways,
        "seo_title": guide.seo_title,
        "seo_description": guide.seo_description,
        "previous": previous,
        "next": next_,
        "series": series or [],
    }


def admin_guide(guide: Guide, category: GuideCategory) -> dict[str, Any]:
    return {
        **guide_card(guide, category),
        "category_id": guide.category_id,
        "category_name": category.name,
        "intro": guide.intro,
        "learning_points": guide.learning_points,
        "requirements": guide.requirements,
        "sections": guide.sections,
        "takeaways": guide.takeaways,
        "seo_title": guide.seo_title,
        "seo_description": guide.seo_description,
        "status": guide.status,
        "view_count": guide.view_count,
        "created_at": guide.created_at,
        "updated_at": guide.updated_at,
    }


def _ordered(rows: list[tuple[Guide, GuideCategory]]) -> list[tuple[Guide, GuideCategory]]:
    return sorted(rows, key=lambda pair: (pair[1].position, pair[1].name, pair[0].position, pair[0].title))


async def load_public_index(db: AsyncSession) -> dict[str, Any]:
    """Every active category plus its published guides, in reading order."""
    categories = (
        await db.execute(select(GuideCategory).where(GuideCategory.is_active.is_(True)).order_by(GuideCategory.position, GuideCategory.name))
    ).scalars().all()
    published = (
        await db.execute(
            select(Guide, GuideCategory)
            .join(GuideCategory, GuideCategory.id == Guide.category_id)
            .where(Guide.status == "published", GuideCategory.is_active.is_(True))
        )
    ).all()

    counts: dict[Any, int] = {}
    cards: list[dict[str, Any]] = []
    for guide, category in _ordered([(row[0], row[1]) for row in published]):
        counts[category.id] = counts.get(category.id, 0) + 1
        cards.append(guide_card(guide, category))

    featured = [card for card in cards if card["is_featured"]][:3]
    if len(featured) < 3:
        featured = cards[:3]
    # A category with nothing published is not a public destination yet.
    visible_categories = [
        category_card(category, counts.get(category.id, 0))
        for category in categories
        if counts.get(category.id, 0) > 0
    ]
    return {
        "categories": visible_categories,
        "guides": cards,
        "featured": featured,
    }


async def load_public_category(db: AsyncSession, slug: str) -> dict[str, Any] | None:
    category = (
        await db.execute(select(GuideCategory).where(GuideCategory.slug == slug, GuideCategory.is_active.is_(True)))
    ).scalar_one_or_none()
    if category is None:
        return None

    rows = (
        await db.execute(
            select(Guide)
            .where(Guide.category_id == category.id, Guide.status == "published")
            .order_by(Guide.position, Guide.title)
        )
    ).scalars().all()

    groups: list[dict[str, Any]] = []
    by_title: dict[str, dict[str, Any]] = {}
    for guide in rows:
        group = by_title.get(guide.group_title)
        if group is None:
            group = {"title": guide.group_title, "guides": []}
            by_title[guide.group_title] = group
            groups.append(group)
        group["guides"].append(guide_card(guide, category))
    if not rows:
        return None
    return {
        "category": category_card(category, len(rows)),
        "groups": groups,
        "total": len(rows),
    }


async def load_public_guide(db: AsyncSession, category_slug: str, slug: str) -> dict[str, Any] | None:
    category = (
        await db.execute(select(GuideCategory).where(GuideCategory.slug == category_slug, GuideCategory.is_active.is_(True)))
    ).scalar_one_or_none()
    if category is None:
        return None
    guide = (
        await db.execute(
            select(Guide).where(Guide.category_id == category.id, Guide.slug == slug, Guide.status == "published")
        )
    ).scalar_one_or_none()
    if guide is None:
        return None

    siblings = (
        await db.execute(
            select(Guide)
            .where(Guide.category_id == category.id, Guide.status == "published")
            .order_by(Guide.position, Guide.title)
        )
    ).scalars().all()
    index = next((position for position, row in enumerate(siblings) if row.id == guide.id), None)
    series_cards = [guide_card(row, category) for row in siblings]
    previous_card = series_cards[index - 1] if index not in (None, 0) else None
    next_card = series_cards[index + 1] if index is not None and index + 1 < len(series_cards) else None

    payload = guide_detail(guide, category, previous=previous_card, next_=next_card, series=series_cards)

    # A read count is a product signal, not a security boundary; a best-effort
    # increment must never stop the page from loading.
    try:
        await db.execute(update(Guide).where(Guide.id == guide.id).values(view_count=Guide.view_count + 1))
        await db.commit()
    except Exception:
        await db.rollback()
    return payload


async def load_admin_categories(db: AsyncSession) -> list[dict[str, Any]]:
    categories = (
        await db.execute(select(GuideCategory).order_by(GuideCategory.position, GuideCategory.name))
    ).scalars().all()
    counts = dict(
        (
            await db.execute(
                select(Guide.category_id, func.count(Guide.id)).group_by(Guide.category_id)
            )
        ).all()
    )
    return [category_card(category, counts.get(category.id, 0)) | {
        "is_active": category.is_active,
        "created_at": category.created_at,
        "updated_at": category.updated_at,
    } for category in categories]


async def load_admin_guides(
    db: AsyncSession,
    *,
    status: str | None = None,
    category_id: Any = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    statement = select(Guide, GuideCategory).join(GuideCategory, GuideCategory.id == Guide.category_id)
    if status:
        statement = statement.where(Guide.status == status)
    if category_id is not None:
        statement = statement.where(Guide.category_id == category_id)
    if query and query.strip():
        needle = f"%{query.strip()}%"
        statement = statement.where(Guide.title.ilike(needle) | Guide.summary.ilike(needle))
    rows = (
        await db.execute(statement.order_by(GuideCategory.position, Guide.position, Guide.title))
    ).all()
    return [admin_guide(guide, category) for guide, category in rows]
