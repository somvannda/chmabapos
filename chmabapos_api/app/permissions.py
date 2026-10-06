"""Permission catalog, default role sets, and resolution.

The catalog is the single source of truth for capability keys, their labels and
groups. Built-in roles are seeded per company with the default sets below, which
reproduce the behaviour of the previous fixed-role guards.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Membership, Role, RolePermission

OWNER_ROLE = "owner"
SYSTEM_ROLES = ("owner", "manager", "inventory_manager", "cashier")

SYSTEM_ROLE_NAMES = {
    "owner": "Owner",
    "manager": "Manager",
    "inventory_manager": "Inventory manager",
    "cashier": "Cashier",
}

# key -> (label, group). Stable identifiers; changing a key is a breaking change.
PERMISSIONS: dict[str, tuple[str, str]] = {
    "sales.create": ("Ring up a sale", "Sales"),
    "sales.refund": ("Refund an order", "Sales"),
    "sales.void_paid_order": ("Cancel or void a paid order", "Sales"),
    "sales.collect_balance": ("Collect a balance / deposit", "Sales"),
    "sales.discount": ("Apply discounts", "Sales"),
    "orders.view": ("View orders", "Orders"),
    "orders.cancel": ("Cancel an unpaid order", "Orders"),
    "customers.manage": ("Manage customers", "Customers"),
    "loyalty.redeem": ("Redeem loyalty points", "Customers"),
    "loyalty.adjust": ("Adjust loyalty points", "Customers"),
    "catalog.view": ("View the catalog", "Catalog"),
    "catalog.manage": ("Manage products, categories, modifiers and combos", "Catalog"),
    "inventory.view": ("View stock", "Inventory"),
    "inventory.manage": ("Adjust, restock and transfer stock", "Inventory"),
    "serials.manage": ("Manage serials", "Inventory"),
    "warranty.manage": ("Manage warranty claims", "Inventory"),
    "trade_ins.manage": ("Manage trade-ins", "Inventory"),
    "purchasing.view": ("View suppliers and purchase orders", "Purchasing"),
    "purchasing.manage": ("Manage suppliers and purchase orders", "Purchasing"),
    "reports.view": ("View reports", "Reports"),
    "reports.consolidated": ("View consolidated reports", "Reports"),
    "reports.gdt": ("Export GDT data", "Reports"),
    "approvals.decide": ("Approve or reject held actions", "Approvals"),
    "approvals.policy_manage": ("Configure the approval policy", "Approvals"),
    "dining.operate": ("Operate the floor and reservations", "Dining"),
    "dining.config": ("Configure dining areas and tables", "Dining"),
    "shifts.manage": ("Open and close shifts", "Operations"),
    "held_orders.use": ("Hold and resume orders", "Operations"),
    "notifications.send": ("Send company summary emails", "Operations"),
    "team.manage": ("Manage the team and roles", "Workspace"),
    "billing.manage": ("Manage billing and plan", "Workspace"),
    "settings.manage": ("Change company and store settings", "Workspace"),
    "audit.view": ("View the activity log", "Workspace"),
    "support.use": ("Use the help assistant and support", "Workspace"),
}

ALL_PERMISSIONS: tuple[str, ...] = tuple(PERMISSIONS)

DEFAULT_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "owner": ALL_PERMISSIONS,
    "manager": (
        "sales.create", "sales.refund", "sales.void_paid_order", "sales.collect_balance", "sales.discount",
        "orders.view", "orders.cancel",
        "customers.manage", "loyalty.redeem", "loyalty.adjust",
        "catalog.view", "catalog.manage",
        "inventory.view", "inventory.manage", "serials.manage", "warranty.manage", "trade_ins.manage",
        "purchasing.view", "purchasing.manage",
        "reports.view", "approvals.decide",
        "dining.operate", "dining.config",
        "shifts.manage", "held_orders.use", "notifications.send",
        "audit.view", "support.use",
    ),
    "inventory_manager": (
        "orders.view", "catalog.view", "catalog.manage",
        "inventory.view", "inventory.manage", "serials.manage", "warranty.manage", "trade_ins.manage",
        "purchasing.view", "purchasing.manage", "reports.view", "approvals.decide", "support.use",
    ),
    "cashier": (
        "sales.create", "sales.collect_balance", "sales.discount",
        "orders.view", "customers.manage", "loyalty.redeem",
        "catalog.view", "inventory.view", "held_orders.use", "shifts.manage", "support.use",
    ),
}


async def seed_system_roles(db: AsyncSession, company_id: UUID) -> None:
    """Create the four built-in roles and their permissions for a company."""
    existing = set((await db.execute(select(Role.key).where(Role.company_id == company_id))).scalars().all())
    for key in SYSTEM_ROLES:
        if key in existing:
            continue
        role = Role(company_id=company_id, key=key, name=SYSTEM_ROLE_NAMES[key], is_system=True)
        db.add(role)
        await db.flush()
        for permission in DEFAULT_ROLE_PERMISSIONS[key]:
            db.add(RolePermission(role_id=role.id, permission=permission))


async def member_permissions(db: AsyncSession, membership: Membership) -> list[str]:
    """The permission set for a membership, from its role."""
    if membership.role == OWNER_ROLE:
        return list(ALL_PERMISSIONS)
    rows = (
        await db.execute(
            select(RolePermission.permission)
            .join(Role, Role.id == RolePermission.role_id)
            .where(Role.company_id == membership.company_id, Role.key == membership.role)
        )
    ).scalars().all()
    return sorted(set(rows))
