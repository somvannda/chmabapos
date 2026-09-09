"""Canonical catalog of billable plan capabilities.

Keys here are stable identifiers used by:
  * the Plan.capabilities JSON map (True = included),
  * backend feature-gating (``require_plan_feature``),
  * the platform-admin plan editor UI.
"""

from typing import Final

# feature_key -> human label used across admin UI + docs
FEATURE_CATALOG: Final[dict[str, str]] = {
    "inventory_management": "Inventory management",
    "purchasing": "Suppliers & purchase orders",
    "khqr_payments": "KHQR / online payments",
    "multi_currency": "Multi-currency & exchange rates",
    "advanced_reports": "Advanced reports & GDT export",
    "loyalty": "Customer loyalty points",
    "barcode_scanning": "Barcode scanning",
    "shift_management": "Shift management",
    "email_receipts": "Email receipts",
    "held_orders": "Hold & resume orders",
    "refunds": "Refunds",
    "receipt_customization": "Custom receipt templates",
    "roles_permissions": "Roles & permissions",
    "priority_support": "Priority support",
}

# Feature keys that are purely promotional (no backend gate).
MARKETING_ONLY: Final[set[str]] = {
    "priority_support",
    "barcode_scanning",
    "receipt_customization",
}

# Bullets shown on every free (non-paying) plan card. Paid plans advertise
# their limits + capabilities instead, since "every plan includes the
# essentials" is stated as shared page copy.
BASE_MARKETING_FEATURES: Final[tuple[str, ...]] = (
    "Basic POS with cash & card",
    "Weekly sales reports",
    "Customer management",
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
        features.append(f"{transaction_limit:,} transactions per month")
    if not (monthly_price or 0) > 0:
        features.extend(BASE_MARKETING_FEATURES)
    for key, label in FEATURE_CATALOG.items():
        if capabilities.get(key):
            features.append(label)
    return features

DEFAULT_FEATURES_BY_PLAN: Final[dict[str, set[str]]] = {
    "free": set(),
    "starter": {
        "inventory_management",
        "purchasing",
        "khqr_payments",
        "multi_currency",
        "advanced_reports",
        "loyalty",
        "barcode_scanning",
        "shift_management",
        "email_receipts",
        "held_orders",
        "refunds",
        "receipt_customization",
    },
    "pro": set(FEATURE_CATALOG.keys()),
}
