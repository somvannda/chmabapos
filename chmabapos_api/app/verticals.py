"""Business-type (vertical) catalog.

A company's ``vertical`` (``Company.vertical`` in ``app/models.py``) tailors the
defaults a brand-new store starts with and, later, the help/support content the
merchant sees. Keys are stable identifiers: they are stored on the company row,
validated on the API boundary, and referenced by the in-app help index.

Keep this module dependency-free (no imports from ``schemas`` or ``models``) so
it stays safe to import from anywhere.
"""
from __future__ import annotations

from typing import Final

# Human labels for the UI and the help index. The order here is the order the
# onboarding dropdown presents them in.
VERTICAL_LABELS: Final[dict[str, str]] = {
    "coffee": "Café / coffee shop",
    "restaurant": "Restaurant / food service",
    "mart": "Mart / grocery",
    "electronics": "Electronics store",
    "shop": "General retail shop",
    "general": "Other / general",
}

# Every accepted ``vertical`` value.
COMPANY_VERTICALS: Final[frozenset[str]] = frozenset(VERTICAL_LABELS)

# Categories seeded into a brand-new store so the catalog is not empty on day
# one. Merchants can rename or delete them; this is only a starting point.
VERTICAL_DEFAULT_CATEGORIES: Final[dict[str, tuple[str, ...]]] = {
    "coffee": ("Coffee", "Tea", "Bakery", "Cold drinks"),
    "restaurant": ("Appetizers", "Main dishes", "Drinks", "Desserts"),
    "mart": ("Beverages", "Snacks", "Household", "Produce"),
    "electronics": ("Phones", "Accessories", "Computers", "Used devices"),
    "shop": ("General",),
    "general": ("General",),
}


def default_categories(vertical: str | None) -> tuple[str, ...]:
    """Return the seed categories for a vertical, falling back to general."""
    return VERTICAL_DEFAULT_CATEGORIES.get(vertical or "", VERTICAL_DEFAULT_CATEGORIES["general"])
