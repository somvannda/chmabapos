"""Business-type (vertical) catalog.

A company's ``vertical`` (``Company.vertical`` in ``app/models.py``) tailors the
defaults a brand-new store starts with: the seed categories, the help/support
content the merchant sees, and the feature "packs" the UI surfaces first (see
``capabilities_for``). Keys are stable identifiers: they are stored on the
company row, validated on the API boundary, and referenced by the in-app help
index.

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

# Feature "packs" a business type turns on. Keys are stable identifiers exposed
# to the client as ``WorkspaceRead.capabilities``; the labels are for the UI.
# They mirror the field-pack table in ``docs/product-model.md`` §5. A capability
# only decides what the UI surfaces first — it never blocks the API, which
# accepts every field for every vertical (see product-model.md §4.1).
CAPABILITY_LABELS: Final[dict[str, str]] = {
    "barcode": "Barcode scanning",
    "brand": "Brand / model",
    "unit_of_measure": "Unit of measure (weight / volume)",
    "variants": "Variants (size, colour, pack)",
    "modifiers": "Modifiers / add-ons",
    "serials": "Serial / IMEI & warranty",
    "batches": "Batches & expiry",
}

# Every valid capability key.
CAPABILITY_KEYS: Final[frozenset[str]] = frozenset(CAPABILITY_LABELS)

# The packs each business type enables by default. "general" is the plain POS
# (core only) and is also the fallback for an unknown value.
VERTICAL_CAPABILITIES: Final[dict[str, tuple[str, ...]]] = {
    "coffee": ("variants", "modifiers"),
    "restaurant": ("variants", "modifiers"),
    "mart": ("barcode", "brand", "unit_of_measure", "variants", "batches"),
    "electronics": ("barcode", "brand", "variants", "serials"),
    "shop": ("barcode", "variants"),
    "general": (),
}


def default_categories(vertical: str | None) -> tuple[str, ...]:
    """Return the seed categories for a vertical, falling back to general."""
    return VERTICAL_DEFAULT_CATEGORIES.get(vertical or "", VERTICAL_DEFAULT_CATEGORIES["general"])


def capabilities_for(vertical: str | None, preferences: dict | None = None) -> tuple[str, ...]:
    """Return the feature packs a store surfaces, in canonical order.

    The company ``vertical`` supplies the defaults. A store may override them
    with ``preferences["capabilities"]`` (a list of keys) so a mixed business —
    say a restaurant with a small electronics counter — can add a pack its
    vertical does not include, or drop one it does. Unknown keys are dropped so
    a stale client value can never widen the result it is allowed to read.
    """
    base = VERTICAL_CAPABILITIES.get(vertical or "", VERTICAL_CAPABILITIES["general"])
    raw = preferences.get("capabilities") if isinstance(preferences, dict) else None
    requested = base if not isinstance(raw, (list, tuple)) else tuple(str(key) for key in raw)
    wanted = {key for key in requested if key in CAPABILITY_KEYS}
    return tuple(key for key in CAPABILITY_LABELS if key in wanted)
