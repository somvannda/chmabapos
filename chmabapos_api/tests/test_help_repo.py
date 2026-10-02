from __future__ import annotations

import pytest
from sqlalchemy import text

from app import support_content
from app.db import SessionLocal
from app.services import help_repo
from app.services import support


def _ids(sections: list[dict]) -> list[str]:
    return [article["id"] for section in sections for article in section["articles"]]


@pytest.mark.asyncio
async def test_seeded_help_articles_match_static_corpus() -> None:
    async with SessionLocal() as db:
        sections = await help_repo.load_sections(db)
    assert sections is not None
    # Same articles and section order as the static seed.
    assert _ids(sections) == _ids(support_content.SUPPORT_SECTIONS)
    assert [section["id"] for section in sections] == [section["id"] for section in support_content.SUPPORT_SECTIONS]


@pytest.mark.asyncio
async def test_db_sections_filter_and_localize_like_static() -> None:
    async with SessionLocal() as db:
        sections = await help_repo.load_sections(db)
    assert sections is not None

    for kwargs in (
        {"vertical": "electronics", "role": "owner", "query": "imei"},
        {"vertical": "general", "role": "owner", "query": "barcode"},
        {"vertical": "general", "role": "cashier"},
        {"vertical": "coffee", "role": "manager", "language": "km"},
        {"vertical": "shop", "role": "owner", "query": "សេរៀល"},
    ):
        assert _ids(support_content.filter_sections(sections, **kwargs)) == _ids(support_content.articles_for(**kwargs))

    khmer = support_content.filter_sections(sections, vertical="general", role="owner", language="km")
    assert khmer[0]["articles"][0]["title"] == support_content.KH_TRANSLATIONS["getting-started.first-sale"]["title"]


@pytest.mark.asyncio
async def test_load_sections_falls_back_to_none_when_empty() -> None:
    # Emptied table must signal the caller to use the static fallback.
    async with SessionLocal() as db:
        try:
            await db.execute(text("DELETE FROM help_articles"))
            assert await help_repo.load_sections(db) is None
        finally:
            await db.rollback()


@pytest.mark.asyncio
async def test_assistant_prompt_uses_db_corpus_identically() -> None:
    async with SessionLocal() as db:
        corpus = await help_repo.load_sections(db)
    assert corpus is not None

    db_system, _messages, db_guides = support.build_prompt(
        question="imei", history=[], vertical="electronics", role="owner", corpus=corpus
    )
    static_system, _messages2, static_guides = support.build_prompt(
        question="imei", history=[], vertical="electronics", role="owner"
    )
    # The assistant is grounded identically whether it reads the DB or the static fallback.
    assert [guide["id"] for guide in db_guides] == [guide["id"] for guide in static_guides]
    assert db_system == static_system


@pytest.mark.asyncio
async def test_point_of_sale_gap_is_localized_in_db() -> None:
    # The seed leaves these two ids in English unless the localize migration
    # UPDATEs them; this guards that the DB serves Khmer for the whole section.
    async with SessionLocal() as db:
        sections = await help_repo.load_sections(db)
    assert sections is not None
    section = next(item for item in sections if item["id"] == "point-of-sale")
    expected_section = support_content.KH_TRANSLATIONS["point-of-sale"]
    assert section["title_km"] == expected_section["title"]
    assert section["blurb_km"] == expected_section["blurb"]

    article = next(item for item in section["articles"] if item["id"] == "pos.customer-display")
    expected = support_content.KH_TRANSLATIONS["pos.customer-display"]
    assert article["title_km"] == expected["title"]
    assert article["steps_km"] == expected["steps"]
    assert article["tip_km"] == expected["tip"]
