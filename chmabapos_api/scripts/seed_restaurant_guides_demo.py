"""Seed a local restaurant workspace for capturing User Guide screenshots.

Local development only. Run with the dev API on :8001:
    python scripts/seed_restaurant_guides_demo.py
"""
from __future__ import annotations

import asyncio
import json
import sys

import httpx
from sqlalchemy import text

from app.db import SessionLocal

BASE = "http://127.0.0.1:8001/api/v1"
EMAIL = "restaurant-demo@example.com"
PASSWORD = "restaurant-demo-password"
COMPANY = "Chmaba Restaurant Guide"


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


async def promote_to_starter() -> None:
    async with SessionLocal() as db:
        await db.execute(
            text(
                "UPDATE subscriptions SET plan_code='starter' "
                "WHERE company_id = (SELECT id FROM companies WHERE name = :name)"
            ),
            {"name": COMPANY},
        )
        await db.commit()


def main() -> None:
    with httpx.Client(timeout=30) as client:
        try:
            login = call(client, "POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD})
        except httpx.HTTPStatusError:
            registered = call(client, "POST", "/auth/register", json={"email": EMAIL, "full_name": "Restaurant Demo", "password": PASSWORD})
            call(client, "POST", "/auth/verify-email", json={"token": registered["dev_verification_token"]})
            login = call(client, "POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD})
        token = login["access_token"]

        try:
            workspace = call(client, "GET", "/workspaces/current", token=token)
        except httpx.HTTPStatusError:
            workspace = call(client, "POST", "/workspaces/setup", token=token, json={
                "company_name": COMPANY,
                "store_name": "Chmaba Kitchen",
                "country": "Cambodia",
                "currency_code": "USD",
                "vertical": "restaurant",
                "store_address": "45 Street 310, Phnom Penh",
                "store_phone": "+855 12 345 678",
                "plan_code": "free",
            })
        store_id = workspace["store"]["id"] if "store" in workspace else workspace["stores"][0]["id"]
        asyncio.run(promote_to_starter())

        categories = call(client, "GET", "/categories", token=token)
        by_name = {row["name"].lower(): row["id"] for row in categories}
        try:
            call(client, "POST", "/workspace/sample-products/clear", token=token, json={})
        except httpx.HTTPStatusError:
            pass

        def ensure_product(name: str, sku: str, price: str, cost: str, category: str):
            rows = call(client, "GET", "/products", token=token, store=store_id)
            found = next((row for row in rows if row["name"].lower() == name.lower()), None)
            if found is None:
                found = call(client, "POST", "/products", token=token, store=store_id, json={
                    "name": name, "sku": sku, "price": price, "cost_price": cost,
                    "category_id": by_name.get(category), "track_inventory": False,
                })
            return found

        rolls = ensure_product("Spring Rolls", "STA-001", "5.50", "1.80", "appetizers")
        chicken = ensure_product("Grilled Chicken", "MAI-001", "9.50", "3.60", "main dishes")
        beef = ensure_product("Beef Lok Lak", "MAI-002", "11.00", "4.80", "main dishes")
        rice = ensure_product("Fried Rice", "MAI-003", "7.50", "2.40", "main dishes")
        mango = ensure_product("Mango Sticky Rice", "DES-001", "5.00", "1.60", "desserts")
        tea = ensure_product("Iced Tea", "DRI-001", "2.50", "0.45", "drinks")

        groups = call(client, "GET", "/modifier-groups", token=token)
        doneness = next((row for row in groups if row["name"] == "Doneness"), None)
        if doneness is None:
            doneness = call(client, "POST", "/modifier-groups", token=token, json={
                "name": "Doneness", "min_select": 1, "max_select": 1, "is_required": True,
                "modifiers": [
                    {"name": "Medium", "price_delta": "0.00", "is_default": True},
                    {"name": "Medium well", "price_delta": "0.00"},
                    {"name": "Well done", "price_delta": "0.00"},
                ],
            })
        call(client, "PATCH", f"/products/{beef['id']}", token=token, store=store_id, json={"modifier_group_id": doneness["id"]})

        # Held tickets reserve stock even for made-to-order dishes, so give the
        # demo dishes a count the kitchen can draw from.
        inventory = call(client, "GET", "/inventory", token=token, store=store_id)
        for row in inventory:
            if float(row.get("on_hand") or 0) <= 0:
                call(client, "POST", f"/inventory/{row['product_id']}/restock", token=token, store=store_id, json={
                    "quantity": "100", "reason": "Restaurant demo stock",
                })

        areas = call(client, "GET", "/dining/areas", token=token, store=store_id)
        ground = next((row for row in areas if row["name"] == "Ground floor"), None)
        if ground is None:
            ground = call(client, "POST", "/dining/areas", token=token, store=store_id, json={"name": "Ground floor", "position": 1})
        terrace = next((row for row in areas if row["name"] == "Terrace"), None)
        if terrace is None:
            terrace = call(client, "POST", "/dining/areas", token=token, store=store_id, json={"name": "Terrace", "position": 2})

        existing_tables = call(client, "GET", "/dining/tables", token=token, store=store_id)
        if not existing_tables:
            for name, area, seats in [("T1", ground, 2), ("T2", ground, 4), ("T3", ground, 4), ("T4", ground, 6), ("T5", terrace, 4), ("T6", terrace, 2)]:
                call(client, "POST", "/dining/tables", token=token, store=store_id, json={"name": name, "area_id": area["id"], "seats": seats})
        tables = call(client, "GET", "/dining/tables", token=token, store=store_id)
        t2 = next(row for row in tables if row["name"] == "T2")
        t4 = next(row for row in tables if row["name"] == "T4")
        t5 = next(row for row in tables if row["name"] == "T5")

        held = call(client, "GET", "/held-orders", token=token, store=store_id)
        if not held:
            call(client, "POST", "/held-orders", token=token, store=store_id, json={
                "label": "T2 · dinner", "order_type": "dine_in", "table_id": t2["id"],
                "items": [
                    {"product_id": rolls["id"], "quantity": "1", "seat": 1, "course": "starters"},
                    {"product_id": beef["id"], "quantity": "1", "seat": 1, "course": "mains", "modifiers": [{"name": "Medium", "price_delta": "0.00"}]},
                    {"product_id": tea["id"], "quantity": "2", "seat": 2, "course": "drinks"},
                ],
            })
            call(client, "POST", "/held-orders", token=token, store=store_id, json={
                "label": "T4 · family", "order_type": "dine_in", "table_id": t4["id"],
                "items": [
                    {"product_id": chicken["id"], "quantity": "2", "seat": 1, "course": "mains"},
                    {"product_id": rice["id"], "quantity": "2", "seat": 2, "course": "mains"},
                    {"product_id": mango["id"], "quantity": "2", "seat": 3, "course": "dessert"},
                ],
            })
            call(client, "PATCH", f"/dining/tables/{t2['id']}", token=token, store=store_id, json={"status": "occupied"})
            call(client, "PATCH", f"/dining/tables/{t4['id']}", token=token, store=store_id, json={"status": "occupied"})
            call(client, "PATCH", f"/dining/tables/{t5['id']}", token=token, store=store_id, json={"status": "reserved"})

        try:
            call(client, "GET", "/shifts/open", token=token, store=store_id)
        except httpx.HTTPStatusError:
            call(client, "POST", "/shifts/open", token=token, store=store_id, json={"opening_float": "200.00"})

        orders = call(client, "GET", "/orders", token=token, store=store_id, params={"limit": 5})
        if not orders:
            for index, product in enumerate([rolls, beef, chicken, rice, mango, tea]):
                call(client, "POST", "/orders", token=token, store=store_id, json={
                    "items": [{"product_id": product["id"], "quantity": 1 if index % 2 else 2}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "50.00"}],
                    "order_type": "dine_in",
                })
            delivery = call(client, "POST", "/orders", token=token, store=store_id, json={
                "items": [{"product_id": chicken["id"], "quantity": 2}],
                "tenders": [{"method": "cash", "currency_code": "USD", "amount": "50.00"}],
                "order_type": "delivery",
                "customer_name": "Sok Dara",
            })
            call(client, "PATCH", f"/orders/{delivery['id']}/delivery", token=token, store=store_id, json={
                "delivery_address": "12 Street 240, Phnom Penh",
                "driver_name": "Vibol",
                "status": "assigned",
            })

        call(client, "PATCH", "/auth/me/preferences", token=token, json={"preferences": {"setup_journey_dismissed": True}})
        print(json.dumps({"email": EMAIL, "password": PASSWORD, "store_id": store_id, "beef_id": beef["id"]}, indent=2))


if __name__ == "__main__":
    main()
