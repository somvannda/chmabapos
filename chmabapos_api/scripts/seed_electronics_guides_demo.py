"""Seed a local electronics workspace for capturing User Guide screenshots."""
from __future__ import annotations

import asyncio
import json
import sys

import httpx
from sqlalchemy import text

from app.db import SessionLocal

BASE = "http://127.0.0.1:8001/api/v1"
EMAIL = "electronics-demo@example.com"
PASSWORD = "electronics-demo-password"
COMPANY = "Chmaba Electronics Guide"


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
            registered = call(client, "POST", "/auth/register", json={"email": EMAIL, "full_name": "Electronics Demo", "password": PASSWORD})
            call(client, "POST", "/auth/verify-email", json={"token": registered["dev_verification_token"]})
            login = call(client, "POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD})
        token = login["access_token"]

        try:
            workspace = call(client, "GET", "/workspaces/current", token=token)
        except httpx.HTTPStatusError:
            workspace = call(client, "POST", "/workspaces/setup", token=token, json={
                "company_name": COMPANY,
                "store_name": "Chmaba Electronics",
                "country": "Cambodia",
                "currency_code": "USD",
                "vertical": "electronics",
                "store_address": "22 Street 214, Phnom Penh",
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

        def ensure_product(name, sku, price, cost, category, barcode, serials=False):
            rows = call(client, "GET", "/products", token=token, store=store_id)
            found = next((row for row in rows if row["name"].lower() == name.lower()), None)
            if found is None:
                found = call(client, "POST", "/products", token=token, store=store_id, json={
                    "name": name, "sku": sku, "price": price, "cost_price": cost,
                    "category_id": by_name.get(category), "barcode": barcode,
                    "brand": "Apple" if "iPhone" in name or "MacBook" in name else "Samsung",
                    "track_inventory": True, "track_serials": serials,
                    "opening_stock": "0" if serials else "30",
                })
            return found

        iphone = ensure_product("iPhone 15 128GB", "PHN-001", "899.00", "740.00", "phones", "8850002000018", True)
        galaxy = ensure_product("Galaxy S24", "PHN-002", "799.00", "650.00", "phones", "8850002000025", True)
        macbook = ensure_product("MacBook Air M3", "COM-001", "1199.00", "980.00", "computers", "8850002000032", True)
        used = ensure_product("iPhone 13 128GB (Used)", "USED-001", "399.00", "280.00", "used devices", "8850002000049", True)
        ensure_product("USB-C Cable 1m", "ACC-001", "12.00", "5.00", "accessories", "8850002000056")

        serial_sets = [
            (iphone, ["IP15-8F2K1", "IP15-8F2K2", "IP15-8F2K3"], "12", None, None),
            (galaxy, ["GS24-7A1B1", "GS24-7A1B2"], "12", None, None),
            (macbook, ["MBA-M3-001", "MBA-M3-002"], "12", None, None),
            (used, ["IP13-USED-1"], "3", "good", 86),
        ]
        for product, numbers, warranty, grade, battery in serial_sets:
            existing = call(client, "GET", f"/products/{product['id']}/serials", token=token, store=store_id)
            if existing:
                continue
            call(client, "POST", f"/products/{product['id']}/serials", token=token, store=store_id, json={
                "serials": [
                    {
                        "serial_number": number,
                        "imei": f"35{product['id'][:6]}{index:04d}",
                        "cost_price": product["cost_price"],
                        "supplier_warranty_months": int(warranty),
                        "customer_warranty_months": int(warranty),
                        "condition_grade": grade,
                        "battery_health": battery,
                    }
                    for index, number in enumerate(numbers)
                ]
            })

        inventory = call(client, "GET", "/inventory", token=token, store=store_id)
        for row in inventory:
            if not row.get("variants") and not row.get("track_serials") and float(row.get("on_hand") or 0) <= 0:
                call(client, "POST", f"/inventory/{row['product_id']}/restock", token=token, store=store_id, json={"quantity": "30", "reason": "Electronics demo stock"})

        try:
            call(client, "GET", "/shifts/open", token=token, store=store_id)
        except httpx.HTTPStatusError:
            call(client, "POST", "/shifts/open", token=token, store=store_id, json={"opening_float": "200.00"})

        orders = call(client, "GET", "/orders", token=token, store=store_id, params={"limit": 5})
        if not orders:
            call(client, "POST", "/orders", token=token, store=store_id, json={
                "items": [{"product_id": iphone["id"], "quantity": 1, "serial_numbers": ["IP15-8F2K1"]}],
                "tenders": [{"method": "cash", "currency_code": "USD", "amount": "1000.00"}],
            })
            for product in [galaxy, macbook, used]:
                call(client, "POST", "/orders", token=token, store=store_id, json={
                    "items": [{"product_id": product["id"], "quantity": 1, "serial_numbers": [serial_sets[[row[0]["id"] for row in serial_sets].index(product["id"])][1][0] if product is not used else "IP13-USED-1"]}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "1500.00"}],
                })

        call(client, "PATCH", "/auth/me/preferences", token=token, json={"preferences": {"setup_journey_dismissed": True}})
        print(json.dumps({"email": EMAIL, "password": PASSWORD, "store_id": store_id, "iphone_id": iphone["id"]}, indent=2))


if __name__ == "__main__":
    main()
