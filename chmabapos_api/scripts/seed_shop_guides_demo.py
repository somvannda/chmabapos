"""Seed a local workspace for the shared "Every shop" guide screenshots.

The four shared guides are about surfaces every business type can reach, so the
demo is deliberately a plain shop with the paid packs a real one buys: a
supplier with one received and one open purchase order, a pending team invite,
an approval policy, and the public storefront switched on.
"""
from __future__ import annotations

import asyncio
import json
import sys

import httpx
from sqlalchemy import text

from app.db import SessionLocal

BASE = "http://127.0.0.1:8001/api/v1"
EMAIL = "shop-guide-demo@example.com"
PASSWORD = "shop-guide-demo-password"
COMPANY = "Chmaba Shop Guide"
STORE_NAME = "Chmaba Shop"


def call(client: httpx.Client, method: str, path: str, token: str | None = None, store: str | None = None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if store:
        headers["X-Store-ID"] = store
    response = client.request(method, f"{BASE}{path}", headers=headers, **kwargs)
    if response.status_code >= 400:
        print(method, path, response.status_code, response.text[:600], file=sys.stderr)
        response.raise_for_status()
    return response.json() if response.content else None


async def promote_to_starter() -> None:
    """Purchasing, online ordering, roles and approvals are Starter features."""
    async with SessionLocal() as db:
        await db.execute(
            text("UPDATE subscriptions SET plan_code='starter' WHERE company_id = (SELECT id FROM companies WHERE name = :name)"),
            {"name": COMPANY},
        )
        await db.commit()


def main() -> None:
    with httpx.Client(timeout=30) as client:
        try:
            login = call(client, "POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD})
        except httpx.HTTPStatusError:
            registered = call(client, "POST", "/auth/register", json={
                "email": EMAIL, "full_name": "Shop Guide Demo", "password": PASSWORD,
            })
            call(client, "POST", "/auth/verify-email", json={"token": registered["dev_verification_token"]})
            login = call(client, "POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD})
        token = login["access_token"]

        try:
            workspace = call(client, "GET", "/workspaces/current", token=token)
        except httpx.HTTPStatusError:
            workspace = call(client, "POST", "/workspaces/setup", token=token, json={
                "company_name": COMPANY,
                "store_name": STORE_NAME,
                "country": "Cambodia",
                "currency_code": "USD",
                "vertical": "shop",
                "store_address": "15 Street 105, Phnom Penh",
                "store_phone": "+855 12 345 678",
                "plan_code": "free",
            })
        store_id = workspace["store"]["id"] if "store" in workspace else workspace["stores"][0]["id"]
        asyncio.run(promote_to_starter())

        # A fresh catalogue so the screenshots do not read like a demo dump.
        categories = call(client, "GET", "/categories", token=token)
        by_name = {row["name"].lower(): row["id"] for row in categories}
        for name, position in [("Drinks", 1), ("Snacks", 2), ("Household", 3)]:
            if name.lower() not in by_name:
                created = call(client, "POST", "/categories", token=token, json={"name": name, "position": position})
                by_name[name.lower()] = created["id"]

        try:
            call(client, "POST", "/workspace/sample-products/clear", token=token, json={})
        except httpx.HTTPStatusError:
            pass

        def ensure_product(name, sku, price, cost, category, barcode, stock=60):
            rows = call(client, "GET", "/products", token=token, store=store_id)
            found = next((row for row in rows if row["name"].lower() == name.lower()), None)
            if found is None:
                found = call(client, "POST", "/products", token=token, store=store_id, json={
                    "name": name, "sku": sku, "price": price, "cost_price": cost,
                    "category_id": by_name.get(category), "barcode": barcode,
                    "track_inventory": True, "opening_stock": str(stock), "reorder_point": 12,
                })
            return found

        water = ensure_product("Bottled Water 1.5L", "DRK-001", "0.75", "0.35", "drinks", "8850004000018", 90)
        cola = ensure_product("Cola Can 330ml", "DRK-002", "1.00", "0.45", "drinks", "8850004000025", 72)
        chips = ensure_product("Potato Chips 60g", "SNK-001", "1.50", "0.70", "snacks", "8850004000032", 48)
        soap = ensure_product("Laundry Soap Bar", "HHD-001", "1.25", "0.60", "household", "8850004000049", 36)

        suppliers = call(client, "GET", "/suppliers", token=token)
        names = {row["name"] for row in suppliers}

        def ensure_supplier(name, contact, phone, email):
            if name in names:
                return next(row for row in suppliers if row["name"] == name)
            return call(client, "POST", "/suppliers", token=token, json={
                "name": name, "contact_name": contact, "phone": phone, "email": email,
            })

        wholesale = ensure_supplier("Phnom Penh Wholesale", "Sokha Chan", "+855 12 900 111", "orders@ppwholesale.example")
        ensure_supplier("Mekong Trading", "Dara Ly", "+855 17 900 222", "sales@mekongtrading.example")

        purchases = call(client, "GET", "/purchases", token=token, store=store_id)
        if not purchases:
            received = call(client, "POST", "/purchases", token=token, store=store_id, json={
                "supplier_id": wholesale["id"],
                "note": "Weekly drinks delivery",
                "items": [
                    {"product_id": water["id"], "quantity": 48, "unit_cost": "0.35"},
                    {"product_id": cola["id"], "quantity": 36, "unit_cost": "0.45"},
                ],
            })
            call(client, "POST", f"/purchases/{received['id']}/receive", token=token, store=store_id, json={})
            call(client, "POST", "/purchases", token=token, store=store_id, json={
                "supplier_id": wholesale["id"],
                "note": "Restock snacks and household",
                "items": [
                    {"product_id": chips["id"], "quantity": 24, "unit_cost": "0.70"},
                    {"product_id": soap["id"], "quantity": 24, "unit_cost": "0.60"},
                ],
            })

        invitations = call(client, "GET", "/team", token=token)
        if not any(row.get("email") == "cashier@chmaba.example" for row in invitations):
            call(client, "POST", "/team/invitations", token=token, json={
                "email": "cashier@chmaba.example", "role": "cashier", "store_ids": [store_id],
            })

        # Approval rules only switch on once the workspace has a team, so the demo
        # accepts the cashier on the owner's behalf instead of leaving it pending.
        pending = call(client, "GET", "/team/invitations", token=token)
        for invitation in pending:
            if invitation.get("email") == "cashier@chmaba.example" and not invitation.get("accepted_at"):
                call(client, "POST", f"/team/invitations/{invitation['id']}/accept-by-owner", token=token)

        call(client, "PUT", "/approval-policy", token=token, json={
            "enabled": True,
            "maker_checker": True,
            "expiry_minutes": 60,
            "notify_in_app": True,
            "notify_telegram": False,
            "rules": {
                "refund": {"mode": "approval", "threshold": "50", "approvers": ["owner", "manager"]},
                "discount": {"mode": "approval", "threshold": "10", "approvers": ["owner", "manager"]},
                "cancel_paid_order": {"mode": "review", "threshold": None, "approvers": ["owner", "manager"]},
                "price_cost_edit": {"mode": "review", "threshold": None, "approvers": ["owner"]},
                "stock_write_off": {"mode": "approval", "threshold": "10", "approvers": ["owner", "manager"]},
                "loyalty_adjust": {"mode": "review", "threshold": "100", "approvers": ["owner", "manager"]},
            },
        })

        # The storefront switch and its public address.
        call(client, "PATCH", f"/stores/{store_id}/public-order", token=token, json={
            "enabled": True, "require_online_payment": False,
        })

        # Branding the public page so the screenshot shows a finished shop, not
        # an empty shell.
        call(client, "PATCH", f"/stores/{store_id}", token=token, json={
            "listed_in_directory": True,
            "storefront": {
                "tagline": "Snacks, drinks and everyday essentials",
                "accent": "emerald",
                "banner": "Order for pickup until 8pm",
                "accept_orders": True,
                "hours": [
                    {"day": day, "open": "08:00", "close": "20:00", "closed": False}
                    for day in ("mon", "tue", "wed", "thu", "fri", "sat")
                ] + [{"day": "sun", "open": "09:00", "close": "18:00", "closed": True}],
            },
        })

        # A real online order, so the Inbox screenshot shows an actual ticket
        # rather than an empty state.
        workspace_store = next(row for row in call(client, "GET", "/stores", token=token) if row["id"] == store_id)
        company = call(client, "GET", "/workspaces/current", token=token)
        company_slug = (company.get("company") or {}).get("slug")
        store_slug = workspace_store.get("slug")
        if company_slug and store_slug:
            try:
                call(client, "POST", f"/public/store/{company_slug}/{store_slug}/orders", json={
                    "items": [
                        {"product_id": chips["id"], "quantity": 2},
                        {"product_id": water["id"], "quantity": 3},
                    ],
                    "customer_name": "Sophea",
                    "customer_note": "Please pack the water in a bag.",
                })
            except httpx.HTTPStatusError:
                pass

        try:
            call(client, "GET", "/shifts/open", token=token, store=store_id)
        except httpx.HTTPStatusError:
            call(client, "POST", "/shifts/open", token=token, store=store_id, json={"opening_float": "150.00"})

        orders = call(client, "GET", "/orders", token=token, store=store_id, params={"limit": 5})
        if not orders:
            for product in (water, cola, chips, cola, water, chips):
                call(client, "POST", "/orders", token=token, store=store_id, json={
                    "items": [{"product_id": product["id"], "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "5.00"}],
                })

        call(client, "PATCH", "/auth/me/preferences", token=token, json={
            "preferences": {"setup_journey_dismissed": True},
        })

        store = call(client, "GET", "/stores", token=token)
        active = next(row for row in store if row["id"] == store_id)
        print(json.dumps({
            "email": EMAIL,
            "password": PASSWORD,
            "store_id": store_id,
            "company_slug": active.get("slug") or active.get("company_slug"),
            "store_slug": active.get("slug"),
        }, indent=2))


if __name__ == "__main__":
    main()
