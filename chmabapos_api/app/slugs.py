"""Public slug generation, validation and reserved-path rules.

A *slug* is the human-readable, shareable part of a public storefront URL:

    https://shops.chmaba.com/<company-slug>/<store-slug>

Slugs are chosen once, printed on signage and pasted into social bios, so the
rules here are deliberately strict: lowercase ``a-z0-9`` with single hyphens,
no leading or trailing hyphen, 3-50 characters. Renames are allowed but the old
slug is remembered (``previous_slugs``) so a redirect can keep the printed link
working.

This module is intentionally free of database and ORM imports so the Alembic
migration that backfills existing rows can reuse exactly the same rules as the
API.
"""

from __future__ import annotations

import re
import unicodedata

MIN_LENGTH = 3
MAX_LENGTH = 50

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NON_SLUG = re.compile(r"[^a-z0-9]+")

# Path segments that already mean something on the public storefront origin, so
# a company slug may never claim one. Mirrors the app's real routes plus the
# files a browser and a crawler ask for.
RESERVED_COMPANY_SLUGS = frozenset(
    {
        "admin",
        "api",
        "app",
        "assets",
        "display",
        "favicon.ico",
        "healthz",
        "login",
        "logout",
        "media",
        "order",
        "orders",
        "robots.txt",
        "signup",
        "sitemap.xml",
        "stores",
        "track",
    }
)

# Reserved one level down, i.e. ``/<company>/<these>``.
RESERVED_STORE_SLUGS = frozenset({"api", "assets", "healthz", "media", "order", "track"})

DEFAULT_COMPANY_SLUG = "company"
DEFAULT_STORE_SLUG = "store"


class InvalidSlug(ValueError):
    """A slug that cannot be used, with a message safe to show a merchant."""


def slugify(value: str | None, *, fallback: str = DEFAULT_STORE_SLUG) -> str:
    """Best-effort slug for a display name.

    Khmer (and other non-Latin) names transliterate to nothing, so callers get
    ``fallback`` and the merchant edits it in Settings.
    """
    text = unicodedata.normalize("NFKD", value or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = _NON_SLUG.sub("-", text.lower()).strip("-")
    if len(text) > MAX_LENGTH:
        text = text[:MAX_LENGTH].strip("-")
    if len(text) < MIN_LENGTH:
        return fallback
    return text


def clean_slug(value: str | None) -> str:
    """Normalise a merchant-supplied slug or raise :class:`InvalidSlug`.

    Raises rather than silently rewriting so the merchant sees why a value was
    rejected; the value is lowercased first because case is not meaningful in
    a host path.
    """
    slug = (value or "").strip().lower()
    if not slug:
        raise InvalidSlug("Enter a web address")
    if len(slug) < MIN_LENGTH:
        raise InvalidSlug(f"Use at least {MIN_LENGTH} characters")
    if len(slug) > MAX_LENGTH:
        raise InvalidSlug(f"Use at most {MAX_LENGTH} characters")
    if not _SLUG_RE.match(slug):
        raise InvalidSlug("Use lowercase letters, numbers and single hyphens only")
    return slug


def allocate_slug(
    base: str,
    taken: set[str],
    reserved: frozenset[str],
    *,
    fallback: str = DEFAULT_STORE_SLUG,
) -> str:
    """Return an unused slug derived from ``base`` and record it in ``taken``.

    Reserved words are escaped by suffixing the fallback (``stores`` becomes
    ``stores-store``) rather than silently dropped, so the merchant still
    recognises their own slug.
    """
    candidate = (base or fallback).strip("-")[:MAX_LENGTH].strip("-") or fallback
    if len(candidate) < MIN_LENGTH:
        candidate = fallback
    if candidate in reserved:
        candidate = f"{candidate}-{fallback}"[:MAX_LENGTH].strip("-")
    stem = candidate
    suffix = 2
    while candidate in taken:
        tail = f"-{suffix}"
        candidate = f"{stem[: MAX_LENGTH - len(tail)]}{tail}".strip("-")
        suffix += 1
    taken.add(candidate)
    return candidate


def ensure_not_reserved(slug: str, reserved: frozenset[str]) -> str:
    """Reject a merchant-supplied slug that collides with a real route."""
    if slug in reserved:
        raise InvalidSlug("That address is reserved — please choose another")
    return slug
