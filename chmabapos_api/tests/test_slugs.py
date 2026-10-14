"""Unit tests for the slug rules (no database required).

These lock the contract that the migration and the API both depend on, so a
change in one place cannot silently drift from the other.
"""
from __future__ import annotations

import pytest

from app import slugs


def test_slugify_strips_punctuation_and_folds_case() -> None:
    assert slugs.slugify("Acme Coffee & Tea!", fallback="store") == "acme-coffee-tea"
    assert slugs.slugify("  Spaced   Out  ", fallback="store") == "spaced-out"
    assert slugs.slugify("Café Résumé", fallback="store") == "cafe-resume"


def test_slugify_falls_back_for_non_latin_and_short_names() -> None:
    # Khmer transliterates to nothing, so the caller gets a usable placeholder
    # rather than an empty slug; the merchant edits it in Settings.
    assert slugs.slugify("ចំបា កាហ្វេ", fallback="store") == "store"
    assert slugs.slugify("ab", fallback="store") == "store"
    assert slugs.slugify("", fallback="company") == "company"
    assert slugs.slugify(None, fallback="company") == "company"


def test_slugify_caps_length() -> None:
    assert len(slugs.slugify("a" * 120, fallback="store")) == slugs.MAX_LENGTH


def test_clean_slug_accepts_and_normalises() -> None:
    assert slugs.clean_slug("  My-Shop  ") == "my-shop"
    assert slugs.clean_slug("shop-2") == "shop-2"
    # Case is not meaningful in a host path, so it is folded rather than rejected.
    assert slugs.clean_slug("UPPER") == "upper"


@pytest.mark.parametrize("value", ["Bad Slug!", "trailing-", "-leading", "double--hyphen", "ab", "", "a" * 51])
def test_clean_slug_rejects_invalid(value: str) -> None:
    with pytest.raises(slugs.InvalidSlug):
        slugs.clean_slug(value)


def test_ensure_not_reserved() -> None:
    with pytest.raises(slugs.InvalidSlug):
        slugs.ensure_not_reserved("stores", slugs.RESERVED_COMPANY_SLUGS)
    # ``stores`` is reserved one level up but is fine as a store slug.
    assert slugs.ensure_not_reserved("stores", slugs.RESERVED_STORE_SLUGS) == "stores"


def test_allocate_slug_escapes_reserved_words() -> None:
    assert slugs.allocate_slug("stores", set(), slugs.RESERVED_COMPANY_SLUGS, fallback="company") == "stores-company"


def test_allocate_slug_dedupes_and_records_taken() -> None:
    taken: set[str] = set()
    assert slugs.allocate_slug("acme", taken, slugs.RESERVED_COMPANY_SLUGS, fallback="company") == "acme"
    assert slugs.allocate_slug("acme", taken, slugs.RESERVED_COMPANY_SLUGS, fallback="company") == "acme-2"
    assert slugs.allocate_slug("acme", taken, slugs.RESERVED_COMPANY_SLUGS, fallback="company") == "acme-3"
    assert taken == {"acme", "acme-2", "acme-3"}
