"""Plan tiers: a single-counter Free, a staffed Starter, a scaling Pro.

The previous catalog advertised three capabilities that gated nothing
(``barcode_scanning``, ``receipt_customization``, ``priority_support``), gave Pro
no feature Starter lacked, and left most of the shipped product - online
ordering, delivery dispatch, combos, serials, batches - free for every account.

This revision rewrites the three built-in plan rows and grandfathers every
in-force subscription, because a capability is stored twice: on the plan row and
inside ``Subscription.plan_terms``. A deploy must not take away something a
workspace already paid for.

Revision ID: b3d7f1a9c2e5
Revises: ba8ee3d27393
Create Date: 2026-10-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3d7f1a9c2e5"
down_revision: Union[str, None] = "ba8ee3d27393"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Frozen copies of the catalogs: a migration must keep doing the same thing even
# if ``app/features.py`` moves on.
NEW_CATALOG = (
    "inventory_management",
    "held_orders",
    "refunds",
    "khqr_payments",
    "multi_currency",
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
    "consolidated_reports",
    "custom_roles",
    "priority_support",
)

FREE_CAPABILITIES = frozenset({
    "inventory_management",
    "held_orders",
    "khqr_payments",
    "multi_currency",
})

STARTER_CAPABILITIES = FREE_CAPABILITIES | {
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

# Capabilities that only exist from this release on. They were either free for
# everyone (so a paying workspace keeps them) or split out of an existing key.
NEWLY_GATED_FEATURES = ("online_ordering", "delivery_dispatch", "combos", "serials_warranty", "batches_expiry")


def _capability_map(enabled) -> dict:
    return {key: key in enabled for key in NEW_CATALOG}


NEW_PLANS = {
    "free": {
        "name": "Free",
        "description": "For one counter, one owner.",
        "monthly_price": "0.00",
        "max_stores": 1,
        "max_members": 1,
        "transaction_limit": 300,
        "capabilities": _capability_map(FREE_CAPABILITIES),
    },
    "starter": {
        "name": "Starter",
        "description": "For a shop with a team.",
        "monthly_price": "4.99",
        "max_stores": 2,
        "max_members": 8,
        "transaction_limit": 5000,
        "capabilities": _capability_map(STARTER_CAPABILITIES),
    },
    "pro": {
        "name": "Pro",
        "description": "For several stores and a bigger team.",
        "monthly_price": "14.99",
        "max_stores": 10,
        "max_members": 40,
        "transaction_limit": 50000,
        "capabilities": _capability_map(NEW_CATALOG),
    },
}

OLD_CATALOG = (
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
    "roles_permissions",
    "table_management",
    "priority_support",
)

OLD_FREE = frozenset({
    "barcode_scanning",
    "held_orders",
    "inventory_management",
    "khqr_payments",
    "loyalty",
    "multi_currency",
    "receipt_customization",
})

OLD_PLANS = {
    "free": {
        "name": "Free",
        "description": "For finding your rhythm.",
        "monthly_price": "0.00",
        "max_stores": 1,
        "max_members": 1,
        "transaction_limit": 3000,
        "capabilities": {key: key in OLD_FREE for key in OLD_CATALOG},
    },
    "starter": {
        "name": "Starter",
        "description": "For teams making moves.",
        "monthly_price": "0.99",
        "max_stores": 5,
        "max_members": 10,
        "transaction_limit": 15000,
        "capabilities": {key: key != "priority_support" for key in OLD_CATALOG},
    },
    "pro": {
        "name": "Pro",
        "description": "For stores ready to scale.",
        "monthly_price": "4.99",
        "max_stores": 50,
        "max_members": 99,
        "transaction_limit": 1000000,
        "capabilities": {key: True for key in OLD_CATALOG},
    },
}

plans = sa.table(
    "plans",
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("description", sa.String()),
    sa.column("monthly_price", sa.Numeric()),
    sa.column("max_stores", sa.Integer()),
    sa.column("max_members", sa.Integer()),
    sa.column("transaction_limit", sa.Integer()),
    sa.column("capabilities", sa.JSON()),
)

subscriptions = sa.table(
    "subscriptions",
    sa.column("id", sa.Uuid()),
    sa.column("plan_code", sa.String()),
    sa.column("status", sa.String()),
    sa.column("plan_terms", sa.JSON()),
)


def _apply_plans(values_by_code: dict) -> None:
    connection = op.get_bind()
    for code, values in values_by_code.items():
        connection.execute(plans.update().where(plans.c.code == code).values(**values))


def upgrade() -> None:
    _apply_plans(NEW_PLANS)

    connection = op.get_bind()
    rows = connection.execute(
        sa.select(subscriptions.c.id, subscriptions.c.plan_code, subscriptions.c.plan_terms).where(
            subscriptions.c.status == "active",
            subscriptions.c.plan_terms.is_not(None),
        )
    ).all()
    for row in rows:
        terms = dict(row.plan_terms or {})
        capabilities = dict(terms.get("capabilities") or {})
        had_advanced = bool(capabilities.get("advanced_reports"))
        had_roles = bool(capabilities.get("roles_permissions"))
        if row.plan_code != "free":
            # Newly gated features were free for every account before this
            # release, so a workspace that has paid for its current period keeps
            # them until the period ends and the plan row takes over.
            for key in NEWLY_GATED_FEATURES:
                capabilities[key] = True
        # Split-out keys follow the capability they were carved from, so an
        # existing Starter subscriber keeps multi-store reports and custom roles.
        capabilities["consolidated_reports"] = had_advanced
        capabilities["custom_roles"] = had_roles
        capabilities.pop("barcode_scanning", None)
        capabilities.pop("receipt_customization", None)
        terms["capabilities"] = capabilities
        connection.execute(
            subscriptions.update().where(subscriptions.c.id == row.id).values(plan_terms=terms)
        )


def downgrade() -> None:
    _apply_plans(OLD_PLANS)

    connection = op.get_bind()
    rows = connection.execute(
        sa.select(subscriptions.c.id, subscriptions.c.plan_terms).where(
            subscriptions.c.status == "active",
            subscriptions.c.plan_terms.is_not(None),
        )
    ).all()
    for row in rows:
        terms = dict(row.plan_terms or {})
        capabilities = dict(terms.get("capabilities") or {})
        for key in NEWLY_GATED_FEATURES + ("consolidated_reports", "custom_roles"):
            capabilities.pop(key, None)
        terms["capabilities"] = capabilities
        connection.execute(
            subscriptions.update().where(subscriptions.c.id == row.id).values(plan_terms=terms)
        )
