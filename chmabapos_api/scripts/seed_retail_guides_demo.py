"""Seed a local general retail workspace for capturing User Guide screenshots."""
from __future__ import annotations

import asyncio
import json
import sys

import httpx
from sqlalchemy import text

from app.db import SessionLocal

BASE = "http://127.0.0.1:8001/api/v1"
EMAIL = "retail-demo@example.com"
PASSWORD = "retail-demo-password"
COMPANY = "Chmaba Retail Guide"


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
            text("UPDATE subscriptions SET plan_code='starter' WHERE company_id = (SELECT id FROM companies WHERE name = :name)"),
            {"name": COMPANY},
        )
        await db.commit()


def main() -> None:
    with httpx.Client(timeout=30) as client:
        try:
            login = call(client, "POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD})
        except httpx.HTTPStatusError:
            registered = call(client, "POST", "/auth/register", json={"email": EMAIL, "full_name": "Retail Demo", "password": PASSWORD})
            call(client, "POST", "/auth/verify-email", json={"token": registered["dev_verification_token"]})
            login = call(client, "POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD})
        token = login["access_token"]

        try:
            workspace = call(client, "GET", "/workspaces/current", token=token)
        except httpx.HTTPStatusError:
            workspace = call(client, "POST", "/workspaces/setup", token=token, json={
                "company_name": COMPANY,
                "store_name": "Chmaba Retail",
                "country": "Cambodia",
                "currency_code": "USD",
                "vertical": "shop",
                "store_address": "15 Street 105, Phnom Penh",
                "store_phone": "+855 12 345 678",
                "plan_code": "free",
            })
        store_id = workspace["store"]["id"] if "store" in workspace else workspace["stores"][0]["id"]
        asyncio.run(promote_to_starter())

        categories = call(client, "GET", "/categories", token=token)
        by_name = {row["name"].lower(): row["id"] for row in categories}
        for name, position in [("Apparel", 1), ("Home", 2), ("Stationery", 3), ("Gifts", 4)]:
            if name.lower() not in by_name:
                created = call(client, "POST", "/categories", token=token, json={"name": name, "position": position})
                by_name[name.lower()] = created["id"]

        try:
            call(client, "POST", "/workspace/sample-products/clear", token=token, json={})
        except httpx.HTTPStatusError:
            pass

        def ensure_product(name, sku, price, cost, category, barcode, stock=40):
            rows = call(client, "GET", "/products", token=token, store=store_id)
            found = next((row for row in rows if row["name"].lower() == name.lower()), None)
            if found is None:
                found = call(client, "POST", "/products", token=token, store=store_id, json={
                    "name": name, "sku": sku, "price": price, "cost_price": cost,
                    "category_id": by_name.get(category), "barcode": barcode,
                    "track_inventory": True, "opening_stock": str(stock), "reorder_point": 8,
                })
            return found

        tshirt = ensure_product("Cotton T-Shirt", "APP-001", "18.00", "8.00", "apparel", "8850003000012", 0)
        ensure_product("Canvas Tote Bag", "APP-002", "12.00", "5.00", "apparel", "8850003000029")
        ensure_product("Soy Candle", "HOM-001", "15.00", "6.50", "home", "8850003000036")
        ensure_product("Hardcover Notebook", "STA-001", "8.50", "3.20", "stationery", "8850003000043")
        ensure_product("Water Bottle", "GIF-001", "22.00", "9.00", "gifts", "8850003000050")

        products_now = call(client, "GET", "/products", token=token, store=store_id)
        tshirt_now = next(row for row in products_now if row["id"] == tshirt["id"])
        variants = tshirt_now.get("variants") or []
        if not variants:
            call(client, "PUT", f"/products/{tshirt['id']}/variants", token=token, store=store_id, json={"variants": [
                {"sku": "APP-001-S", "name": "Small", "price": "18.00", "cost_price": "8.00", "opening_stock": "12"},
                {"sku": "APP-001-M", "name": "Medium", "price": "18.00", "cost_price": "8.00", "opening_stock": "18"},
                {"sku": "APP-001-L", "name": "Large", "price": "20.00", "cost_price": "8.50", "opening_stock": "10"},
            ]})

        try:
            call(client, "GET", "/shifts/open", token=token, store=store_id)
        except httpx.HTTPStatusError:
            call(client, "POST", "/shifts/open", token=token, store=store_id, json={"opening_float": "200.00"})

        orders = call(client, "GET", "/orders", token=token, store=store_id, params={"limit": 5})
        if not orders:
            variant_ids = [row["id"] for row in variants]
            for index in range(6):
                call(client, "POST", "/orders", token=token, store=store_id, json={
                    "items": [{"product_id": tshirt["id"], "variant_id": variant_ids[index % len(variant_ids)], "quantity": 1}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "50.00"}],
                })

        call(client, "PATCH", "/auth/me/preferences", token=token, json={"preferences": {"setup_journey_dismissed": True}})
        print(json.dumps({"email": EMAIL, "password": PASSWORD, "store_id": store_id}, indent=2))


if __name__ == "__main__":
    main()
