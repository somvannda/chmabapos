"""Canonical catalog of billable plan capabilities.

Keys here are stable identifiers used by:
  * the Plan.capabilities JSON map (True = included),
  * backend feature-gating (``require_plan_feature``),
  * the platform-admin plan editor UI (via ``GET /plans/features``).

A key is permanent. It is persisted on ``Plan.capabilities`` **and** inside every
``Subscription.plan_terms`` snapshot, so renaming one silently strips a paid
feature from in-force subscribers until their next renewal. Change the label,
not the key; the only safe rename is one shipped with a migration that also
rewrites the snapshots.

Order is display order: the marketing bullets and the plan editor both read this
dict in order, so it runs from daily selling outward to scale and governance.
"""

from typing import Final

# feature_key -> human label used across admin UI + docs
FEATURE_CATALOG: Final[dict[str, str]] = {
    "inventory_management": "Inventory management",
    "held_orders": "Hold & resume orders",
    "refunds": "Refunds",
    "khqr_payments": "KHQR / online payments",
    "multi_currency": "Multi-currency & exchange rates",
    "shift_management": "Shift management",
    "email_receipts": "Email receipts",
    "purchasing": "Suppliers & purchase orders",
    "advanced_reports": "Advanced reports & exports",
    "roles_permissions": "Staff accounts & store access",
    "table_management": "Restaurant mode (tables, kitchen, delivery)",
    "loyalty": "Customer loyalty points",
    "online_ordering": "Online ordering & QR menu",
    "delivery_dispatch": "Delivery dispatch board",
    "combos": "Combos & meal deals",
    "serials_warranty": "Serials, warranty & trade-in",
    "batches_expiry": "Batches & expiry",
    "consolidated_reports": "Multi-store consolidated reports",
    "custom_roles": "Custom roles & approvals",
    "priority_support": "Priority support",
}

# Feature keys that do not hard-gate an endpoint: ``priority_support`` only
# changes how a support escalation is flagged, so it is advertised and recorded
# but never refuses a request.
MARKETING_ONLY: Final[frozenset[str]] = frozenset({"priority_support"})

# Bullets shown on every Free card, on top of its capabilities. These are core
# POS behaviours that are not billable and therefore have no capability key;
# without them a Free card would read as if it could not take a sale.
BASE_MARKETING_FEATURES: Final[tuple[str, ...]] = (
    "Basic POS with cash",
    "Barcode & SKU search",
    "Receipt printing & templates",
    "Customer management",
    "Weekly sales reports",
)


def derive_plan_marketing_features(
    *,
    max_stores: int,
    max_members: int,
    transaction_limit: int,
    capabilities: dict,
    monthly_price,
) -> list[str]:
    """Build the marketing bullet list purely from a plan's structured fields.

    Marketing copy is intentionally not stored: bullets always reflect the real
    limits and enabled capabilities so public pricing cannot drift from what is
    actually enforced (``features.py`` labels are the single source of truth).
    """
    features: list[str] = []
    features.append("1 store" if max_stores <= 1 else f"Up to {max_stores} stores")
    features.append("1 owner account" if max_members <= 1 else f"Up to {max_members} team members")
    if (transaction_limit or 0) > 0:
        # ``transaction_limit`` is a monthly rate; a longer cycle buys more
        # months, not a bigger monthly allowance. Say "per month" for every
        # plan so the bullet matches what is enforced.
        features.append(f"{transaction_limit:,} transactions per month")
    if not (monthly_price or 0) > 0:
        features.extend(BASE_MARKETING_FEATURES)
    for key, label in FEATURE_CATALOG.items():
        if capabilities.get(key):
            features.append(label)
    return features


# The Free tier is a complete single counter: it can take money, hold a ticket
# and track stock, but not run a second location, a second person or the
# commerce/scale surface. Every key it omits is a documented upgrade reason.
_FREE_FEATURES: Final[frozenset[str]] = frozenset({
    "inventory_management",
    "held_orders",
    "khqr_payments",
    "multi_currency",
})

# Starter is "a real shop with staff": the day-to-day operating surface,
# including the vertical depth (serials, batches, restaurant, combos) that used
# to be free for every account.
_STARTER_FEATURES: Final[frozenset[str]] = _FREE_FEATURES | {
    "refunds",
    "shift_management",
    "email_receipts",
    "purchasing",
    "advanced_reports",
    "roles_permissions",
    "table_management",
    "loyalty",
    "online_ordering",
    "delivery_dispatch",
    "combos",
    "serials_warranty",
    "batches_expiry",
}

# Pro adds scale and governance on top: every capability in the catalog.
DEFAULT_FEATURES_BY_PLAN: Final[dict[str, frozenset[str]]] = {
    "free": _FREE_FEATURES,
    "starter": _STARTER_FEATURES,
    "pro": frozenset(FEATURE_CATALOG),
}
