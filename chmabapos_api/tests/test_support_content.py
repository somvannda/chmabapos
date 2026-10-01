from __future__ import annotations

from app import support_content


def _ids(sections: list[dict]) -> set[str]:
    return {article["id"] for section in sections for article in section["articles"]}


def test_articles_filter_by_vertical() -> None:
    electronics = _ids(support_content.articles_for(vertical="electronics", role="owner"))
    assert "electronics.serials" in electronics

    coffee = _ids(support_content.articles_for(vertical="coffee", role="owner"))
    assert "electronics.serials" not in coffee
    assert "getting-started.first-sale" in coffee


def test_articles_filter_by_role() -> None:
    cashier = _ids(support_content.articles_for(vertical="general", role="cashier"))
    assert "getting-started.first-sale" in cashier
    assert "team.invite" not in cashier  # owner-only


def test_articles_search_is_scoped_to_available_content() -> None:
    # "IMEI" only exists in the electronics serials article.
    assert support_content.articles_for(vertical="general", role="owner", query="imei") == []
    matches = _ids(support_content.articles_for(vertical="electronics", role="owner", query="imei"))
    assert matches == {"electronics.serials"}


def test_starter_prompts_fall_back_and_never_empty_for_cashier() -> None:
    assert support_content.starter_prompts_for(vertical="electronics", role="owner")
    assert support_content.starter_prompts_for(vertical="unknown", role="owner") == support_content.STARTER_PROMPTS["general"]
    assert support_content.starter_prompts_for(vertical="electronics", role="cashier")
