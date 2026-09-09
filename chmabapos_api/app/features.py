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
