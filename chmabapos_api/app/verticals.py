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
    "tables": "Tables & floor plan",
    "serials": "Serial / IMEI & warranty",
    "batches": "Batches & expiry",
}

# Every valid capability key.
CAPABILITY_KEYS: Final[frozenset[str]] = frozenset(CAPABILITY_LABELS)

# The packs each business type enables by default. "general" is the plain POS
# (core only) and is also the fallback for an unknown value.
VERTICAL_CAPABILITIES: Final[dict[str, tuple[str, ...]]] = {
    "coffee": ("variants", "modifiers"),
    "restaurant": ("variants", "modifiers", "tables"),
    "mart": ("barcode", "brand", "unit_of_measure", "variants", "batches"),
    "electronics": ("barcode", "brand", "variants", "serials"),
    "shop": ("barcode", "variants"),
    "general": (),
}


def default_categories(vertical: str | None) -> tuple[str, ...]:
    """Return the seed categories for a vertical, falling back to general."""
    return VERTICAL_DEFAULT_CATEGORIES.get(vertical or "", VERTICAL_DEFAULT_CATEGORIES["general"])


# A couple of demo items seeded alongside the categories so a brand-new store
# is not an empty room: the owner can ring up a sale immediately and see the
# product work before entering their own catalogue. ``category`` must match one
# of ``default_categories``. These rows are flagged ``is_sample`` and never
# count as "the merchant added a product".
VERTICAL_DEFAULT_PRODUCTS: Final[dict[str, tuple[dict[str, object], ...]]] = {
    "coffee": (
        {"name": "Sample Iced Latte", "category": "Coffee", "price": "2.50", "cost_price": "1.00", "unit": "each", "opening_stock": 20},
        {"name": "Sample Cappuccino", "category": "Coffee", "price": "2.00", "cost_price": "0.80", "unit": "each", "opening_stock": 20},
        {"name": "Sample Iced Tea", "category": "Tea", "price": "1.50", "cost_price": "0.50", "unit": "each", "opening_stock": 20},
    ),
    "restaurant": (
        {"name": "Sample Beef Lok Lak", "category": "Main dishes", "price": "3.50", "cost_price": "1.80", "unit": "each", "opening_stock": 15},
        {"name": "Sample Spring Rolls", "category": "Appetizers", "price": "2.00", "cost_price": "0.90", "unit": "each", "opening_stock": 20},
        {"name": "Sample Iced Tea", "category": "Drinks", "price": "1.00", "cost_price": "0.30", "unit": "each", "opening_stock": 30},
    ),
    "mart": (
        {"name": "Sample Bottled Water", "category": "Beverages", "price": "0.50", "cost_price": "0.25", "unit": "each", "opening_stock": 48},
        {"name": "Sample Instant Noodles", "category": "Snacks", "price": "0.75", "cost_price": "0.45", "unit": "each", "opening_stock": 40},
        {"name": "Sample Dish Soap", "category": "Household", "price": "1.20", "cost_price": "0.70", "unit": "each", "opening_stock": 24},
    ),
    "electronics": (
        {"name": "Sample Phone Case", "category": "Accessories", "price": "5.00", "cost_price": "2.00", "unit": "each", "opening_stock": 10},
        {"name": "Sample USB-C Cable", "category": "Accessories", "price": "3.50", "cost_price": "1.20", "unit": "each", "opening_stock": 15},
        {"name": "Sample Power Bank", "category": "Accessories", "price": "12.00", "cost_price": "7.00", "unit": "each", "opening_stock": 8},
    ),
    "shop": (
        {"name": "Sample T-Shirt", "category": "General", "price": "5.00", "cost_price": "2.50", "unit": "each", "opening_stock": 12},
        {"name": "Sample Tote Bag", "category": "General", "price": "4.00", "cost_price": "1.80", "unit": "each", "opening_stock": 12},
        {"name": "Sample Water Bottle", "category": "General", "price": "3.00", "cost_price": "1.20", "unit": "each", "opening_stock": 12},
    ),
    "general": (
        {"name": "Sample T-Shirt", "category": "General", "price": "5.00", "cost_price": "2.50", "unit": "each", "opening_stock": 12},
        {"name": "Sample Tote Bag", "category": "General", "price": "4.00", "cost_price": "1.80", "unit": "each", "opening_stock": 12},
        {"name": "Sample Water Bottle", "category": "General", "price": "3.00", "cost_price": "1.20", "unit": "each", "opening_stock": 12},
    ),
}


def sample_products(vertical: str | None) -> tuple[dict[str, object], ...]:
    """Return the demo products for a vertical, falling back to general."""
    return VERTICAL_DEFAULT_PRODUCTS.get(vertical or "", VERTICAL_DEFAULT_PRODUCTS["general"])


def default_capabilities(vertical: str | None) -> tuple[str, ...]:
    """Return the packs a business type turns on, in canonical order.

    This is the vertical's own defaults, before any per-store override, so the
    UI can label each pack ("on by default" vs "added by you") and offer a
    "reset to defaults" action without duplicating the mapping client-side.
    """
    base = VERTICAL_CAPABILITIES.get(vertical or "", VERTICAL_CAPABILITIES["general"])
    wanted = {key for key in base if key in CAPABILITY_KEYS}
    return tuple(key for key in CAPABILITY_LABELS if key in wanted)


def _clean_capability_keys(keys: object) -> set[str]:
    """Keep only known capability keys, so a stale client value never widens access."""
    if not isinstance(keys, (list, tuple, set, frozenset)):
        return set()
    return {str(key) for key in keys if str(key) in CAPABILITY_KEYS}


def capabilities_for(vertical: str | None, preferences: dict | None = None) -> tuple[str, ...]:
    """Return the feature packs a store surfaces, in canonical order.

    The company ``vertical`` supplies the defaults. A store may override them so
    a mixed business — say a restaurant with a small electronics counter — can
    add a pack its vertical does not include, or drop one it does. Unknown keys
    are dropped so a stale client value can never widen the result.

    Two override shapes are honoured, most-recent first:

    * ``preferences["capability_overrides"]`` = ``{"added": [...], "removed": [...]}``
      — a delta against the business-type defaults. Preferred, because the store
      keeps tracking ``Company.vertical`` when the merchant changes it.
    * ``preferences["capabilities"]`` = ``[...]`` — a legacy absolute list that
      replaces the defaults. Still honoured for stores saved before the delta
      model so nothing changes under them.
    """
    base = default_capabilities(vertical)
    prefs = preferences if isinstance(preferences, dict) else {}
    overrides = prefs.get("capability_overrides")
    if isinstance(overrides, dict):
        added = _clean_capability_keys(overrides.get("added"))
        removed = _clean_capability_keys(overrides.get("removed"))
        wanted = (set(base) | added) - removed
    else:
        raw = prefs.get("capabilities")
        wanted = _clean_capability_keys(raw) if isinstance(raw, (list, tuple)) else set(base)
    return tuple(key for key in CAPABILITY_LABELS if key in wanted)
