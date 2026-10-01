"""Retrieval / grounding eval for the support assistant.

A small, curated table of questions and the guide(s) the assistant should be
grounded in. It is deliberately keyword-shaped because retrieval matches text
directly; if a future change alters retrieval, localization, or vertical/role
filtering, these cases fail instead of silently degrading answers.

This is not a model-quality eval — the provider is never called. It pins the
*grounding contract*: which sources reach the prompt for a given caller.
"""
from __future__ import annotations

import pytest

from app import support_content
from app.services import support


def _ids(sections: list[dict]) -> set[str]:
    return {article["id"] for section in sections for article in section["articles"]}


# (vertical, role, query, guide ids that must be retrieved)
RETRIEVAL_CASES = [
    ("electronics", "owner", "imei", {"electronics.serials"}),
    ("electronics", "owner", "battery", {"electronics.warranty"}),
    ("general", "owner", "reorder", {"inventory.low-stock"}),
    ("general", "owner", "barcode", {"getting-started.add-products"}),
    ("general", "owner", "receipt", {"getting-started.first-sale"}),
    ("general", "owner", "invite", {"team.invite"}),
    # Keyword synonyms resolve to the right guide even though the words are not
    # in the article text.
    ("general", "owner", "checkout", {"getting-started.first-sale"}),
    ("coffee", "owner", "menu", {"getting-started.add-products"}),
    ("general", "owner", "downgrade", {"billing.change-plan"}),
    ("general", "owner", "employee", {"team.invite"}),
]


@pytest.mark.parametrize("vertical,role,query,expected", RETRIEVAL_CASES)
def test_retrieval_returns_expected_guide(vertical: str, role: str, query: str, expected: set[str]) -> None:
    ids = _ids(support_content.articles_for(vertical=vertical, role=role, query=query))
    assert expected <= ids, f"{query!r} should retrieve {expected}, got {ids}"


def test_retrieval_is_scoped_by_vertical() -> None:
    # An electronics-only guide never leaks into a shop's grounding.
    ids = _ids(support_content.articles_for(vertical="shop", role="owner", query="imei"))
    assert "electronics.serials" not in ids


def test_natural_language_question_falls_back_to_the_caller_guides() -> None:
    # A question with no keyword overlap matches nothing...
    assert _ids(support_content.articles_for(vertical="coffee", role="owner", query="How do I fly a drone?")) == set()
    # ...but build_prompt still grounds the caller on their full guide set, and
    # tells the model this question was not covered.
    system, _messages, guides = support.build_prompt(
        question="How do I fly a drone?", history=[], vertical="coffee", role="owner"
    )
    assert "getting-started.first-sale" in [guide["id"] for guide in guides]
    assert "no guide matched" in system


def test_build_prompt_does_not_fail_loudly_when_matched() -> None:
    system, _messages, _guides = support.build_prompt(question="checkout", history=[], vertical="general", role="owner")
    assert "no guide matched" not in system


def test_build_prompt_grounds_the_matched_guide() -> None:
    system, _messages, guides = support.build_prompt(question="barcode", history=[], vertical="mart", role="owner")
    assert "getting-started.add-products" in [guide["id"] for guide in guides]
    assert "Add your products" in system


def test_build_prompt_includes_data_and_language_directives() -> None:
    system, _messages, _guides = support.build_prompt(
        question="how much stock is left?",
        history=[],
        vertical="general",
        role="owner",
        live_data="Items at or below their reorder point:\n- Widget: 2 on hand",
        language="km",
    )
    assert "LIVE STORE DATA" in system
    assert "Widget: 2 on hand" in system
    assert "Khmer" in system
