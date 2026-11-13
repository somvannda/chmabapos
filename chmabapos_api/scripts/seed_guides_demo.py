"""Create (or reuse) a demo coffee workspace for capturing guide screenshots.

Run against a local dev API:  python scripts/seed_guides_demo.py
It is idempotent: a second run logs in, repairs missing variants/modifiers and
returns the same ids. The account is local-only; never run this in production.
"""
from __future__ import annotations

import json
import sys

import httpx

BASE = "http://127.0.0.1:8001/api/v1"
EMAIL = "guide-demo@example.com"
PASSWORD = "guide-demo-password"


def call(client: httpx.Client, method: str, path: str, token: str | None = None, store: str | None = None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if store:
        headers["X-Store-ID"] = store
    response = client.request(method, f"{BASE}{path}", headers=headers, **kwargs)
    if response.status_code >= 400:
        print(method, path, response.status_code, response.text[:500], file=sys.stderr)
        response.raise_for_status()
    return response.json() if response.content else None


def main() -> None:
    with httpx.Client(timeout=30) as client:
        # Log in if the demo account already exists, otherwise register one.
        try:
            login = call(client, "POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD})
        except httpx.HTTPStatusError:
            registered = call(client, "POST", "/auth/register", json={"email": EMAIL, "full_name": "Guide Demo", "password": PASSWORD})
            call(client, "POST", "/auth/verify-email", json={"token": registered["dev_verification_token"]})
            login = call(client, "POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD})
        token = login["access_token"]

        try:
            workspace = call(client, "GET", "/workspaces/current", token=token)
        except httpx.HTTPStatusError:
            workspace = call(client, "POST", "/workspaces/setup", token=token, json={
                "company_name": "Chmaba Coffee Guide",
                "store_name": "Chmaba Coffee",
                "country": "Cambodia",
                "currency_code": "USD",
                "vertical": "coffee",
                "store_address": "12 Street 240, Phnom Penh",
                "store_phone": "+855 12 345 678",
                "plan_code": "free",
            })
        store_id = workspace["store"]["id"] if "store" in workspace else workspace["stores"][0]["id"]

        categories = call(client, "GET", "/categories", token=token)
        category_by_name = {row["name"].lower(): row["id"] for row in categories}
        try:
            call(client, "POST", "/workspace/sample-products/clear", token=token, json={})
        except httpx.HTTPStatusError:
            pass

        def ensure_product(name: str, sku: str, price: str, cost: str, category: str, track: bool = False):
            rows = call(client, "GET", "/products", token=token, store=store_id)
            found = next((row for row in rows if row["name"].lower() == name.lower()), None)
            if found is None:
                found = call(client, "POST", "/products", token=token, store=store_id, json={
                    "name": name, "sku": sku, "price": price, "cost_price": cost,
                    "category_id": category_by_name.get(category), "track_inventory": track,
                    "opening_stock": "100" if track else "0",
                })
            else:
                call(client, "PATCH", f"/products/{found['id']}", token=token, store=store_id, json={"cost_price": cost, "track_inventory": track})
            return found

        iced = ensure_product("Iced Latte", "COF-001", "4.50", "1.05", "coffee")
        ensure_product("Hot Latte", "COF-002", "4.00", "0.95", "coffee")
        ensure_product("Americano", "COF-003", "3.50", "0.60", "coffee")
        ensure_product("Matcha Cloud", "TEA-004", "5.25", "1.55", "tea")
        ensure_product("Earl Grey", "TEA-001", "3.75", "0.70", "tea")
        ensure_product("Butter Croissant", "BAK-002", "3.20", "1.25", "bakery", True)
        ensure_product("Cinnamon Roll", "BAK-004", "3.80", "1.45", "bakery", True)
        ensure_product("Yuzu Sparkler", "COL-011", "4.75", "1.10", "cold drinks")
        groups = call(client, "GET", "/modifier-groups", token=token)
        milk = next((row for row in groups if row["name"] == "Milk"), None)
        if milk is None:
            milk = call(client, "POST", "/modifier-groups", token=token, json={
                "name": "Milk",
                "min_select": 1,
                "max_select": 1,
                "is_required": True,
                "modifiers": [
                    {"name": "Whole milk", "price_delta": "0.00", "is_default": True},
                    {"name": "Oat milk", "price_delta": "0.50"},
                    {"name": "Soy milk", "price_delta": "0.50"},
                    {"name": "Almond milk", "price_delta": "0.75"},
                ],
            })
        call(client, "PATCH", f"/products/{iced['id']}", token=token, store=store_id, json={"modifier_group_id": milk["id"]})

        variants = call(client, "PUT", f"/products/{iced['id']}/variants", token=token, store=store_id, json={"variants": [
            {"sku": "COF-001-12", "name": "12 oz", "price": "3.75", "cost_price": "0.85", "opening_stock": "100"},
            {"sku": "COF-001-16", "name": "16 oz", "price": "4.50", "cost_price": "1.05", "opening_stock": "100"},
            {"sku": "COF-001-20", "name": "20 oz", "price": "5.25", "cost_price": "1.25", "opening_stock": "100"},
        ]})

        variant_rows = variants.get("variants", []) if isinstance(variants, dict) else variants
        medium = next((row for row in variant_rows if row["name"] == "16 oz"), variant_rows[0] if variant_rows else None)

        # Every product needs a believable count so the register and inventory
        # screens do not show "0 left" in guide screenshots.
        inventory = call(client, "GET", "/inventory", token=token, store=store_id)
        for row in inventory:
            if not row.get("variants") and float(row.get("on_hand") or 0) <= 0:
                call(client, "POST", f"/inventory/{row['product_id']}/restock", token=token, store=store_id, json={"quantity": "100", "reason": "Guide demo stock"})

        call(client, "PATCH", "/auth/me/preferences", token=token, json={"preferences": {"setup_journey_dismissed": True}})
        # A couple of real sales make the Orders and Reports screens meaningful.
        existing_orders = call(client, "GET", "/orders", token=token, store=store_id, params={"limit": 5})
        if not existing_orders:
            try:
                call(client, "GET", "/shifts/open", token=token, store=store_id)
            except httpx.HTTPStatusError:
                call(client, "POST", "/shifts/open", token=token, store=store_id, json={"opening_float": "200.00", "note": "Guide demo"})
            for index in range(6):
                call(client, "POST", "/orders", token=token, store=store_id, json={
                    "items": [{
                        "product_id": iced["id"],
                        "variant_id": medium["id"] if medium else None,
                        "quantity": 1 if index % 2 == 0 else 2,
                        "modifiers": [{"name": "Oat milk", "price_delta": "0.50"}] if index % 2 == 0 else [],
                    }],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "50.00"}],
                    "order_type": "takeaway",
                })

        print(json.dumps({"email": EMAIL, "password": PASSWORD, "store_id": store_id, "product_id": iced["id"], "modifier_group_id": milk["id"], "variants": [row["name"] for row in variant_rows]}, indent=2))


if __name__ == "__main__":
    main()




