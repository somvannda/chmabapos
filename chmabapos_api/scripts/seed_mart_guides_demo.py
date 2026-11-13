"""Seed a local mart workspace for capturing User Guide screenshots.

Local development only. Run with the dev API on :8001:
    PYTHONPATH=chmabapos_api python chmabapos_api/scripts/seed_mart_guides_demo.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, timedelta

import httpx
from sqlalchemy import text

from app.db import SessionLocal

BASE = "http://127.0.0.1:8001/api/v1"
EMAIL = "mart-demo@example.com"
PASSWORD = "mart-demo-password"
COMPANY = "Chmaba Mart Guide"


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
            registered = call(client, "POST", "/auth/register", json={"email": EMAIL, "full_name": "Mart Demo", "password": PASSWORD})
            call(client, "POST", "/auth/verify-email", json={"token": registered["dev_verification_token"]})
            login = call(client, "POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD})
        token = login["access_token"]

        try:
            workspace = call(client, "GET", "/workspaces/current", token=token)
        except httpx.HTTPStatusError:
            workspace = call(client, "POST", "/workspaces/setup", token=token, json={
                "company_name": COMPANY,
                "store_name": "Chmaba Mart",
                "country": "Cambodia",
                "currency_code": "USD",
                "vertical": "mart",
                "store_address": "78 Street 271, Phnom Penh",
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

        def ensure_product(name, sku, price, cost, category, barcode, unit="each", stock=50):
            rows = call(client, "GET", "/products", token=token, store=store_id)
            found = next((row for row in rows if row["name"].lower() == name.lower()), None)
            if found is None:
                found = call(client, "POST", "/products", token=token, store=store_id, json={
                    "name": name, "sku": sku, "price": price, "cost_price": cost,
                    "category_id": by_name.get(category), "barcode": barcode, "unit": unit,
                    "track_inventory": True, "opening_stock": str(stock), "reorder_point": 10,
                })
            return found

        cola = ensure_product("Coca-Cola 330ml", "BEV-001", "0.75", "0.45", "beverages", "8850001000011")
        milk = ensure_product("Oat Milk 1L", "BEV-002", "2.80", "1.80", "beverages", "8850001000028")
        rice = ensure_product("Jasmine Rice 5kg", "GRO-001", "8.50", "5.80", "produce", "8850001000035")
        chips = ensure_product("Potato Chips", "SNA-001", "1.20", "0.70", "snacks", "8850001000042")
        soap = ensure_product("Dish Soap", "HOU-001", "2.10", "1.20", "household", "8850001000059")
        bananas = ensure_product("Bananas", "PRO-001", "1.20", "0.60", "produce", "8850001000066", "kg", 25)

        inventory = call(client, "GET", "/inventory", token=token, store=store_id)
        for row in inventory:
            if float(row.get("on_hand") or 0) <= 0:
                call(client, "POST", f"/inventory/{row['product_id']}/restock", token=token, store=store_id, json={"quantity": "40", "reason": "Mart demo stock"})

        batches = call(client, "GET", f"/products/{milk['id']}/batches", token=token, store=store_id)
        if not batches:
            call(client, "POST", f"/products/{milk['id']}/batches", token=token, store=store_id, json={"batches": [
                {"batch_code": "MILK-2411", "expiry_date": str(date.today() + timedelta(days=9)), "quantity_on_hand": "12", "cost_price": "1.80"},
                {"batch_code": "MILK-2501", "expiry_date": str(date.today() + timedelta(days=45)), "quantity_on_hand": "18", "cost_price": "1.80"},
            ]})

        suppliers = call(client, "GET", "/suppliers", token=token)
        supplier = next((row for row in suppliers if row["name"] == "Angkor Distribution"), None)
        if supplier is None:
            supplier = call(client, "POST", "/suppliers", token=token, json={"name": "Angkor Distribution", "contact_name": "Dara", "phone": "+855 12 777 888"})

        purchases = call(client, "GET", "/purchases", token=token, store=store_id)
        if not purchases:
            po = call(client, "POST", "/purchases", token=token, store=store_id, json={
                "supplier_id": supplier["id"],
                "items": [{"product_id": milk["id"], "quantity": 24, "unit_cost": "1.80"}],
                "note": "Weekly dairy delivery",
            })
            call(client, "POST", f"/purchases/{po['id']}/receive", token=token, store=store_id, json={})

        try:
            call(client, "GET", "/shifts/open", token=token, store=store_id)
        except httpx.HTTPStatusError:
            call(client, "POST", "/shifts/open", token=token, store=store_id, json={"opening_float": "200.00"})

        orders = call(client, "GET", "/orders", token=token, store=store_id, params={"limit": 5})
        if not orders:
            for index, product in enumerate([cola, milk, chips, rice, soap, bananas]):
                call(client, "POST", "/orders", token=token, store=store_id, json={
                    "items": [{"product_id": product["id"], "quantity": 1 if product is not bananas else "1.5"}],
                    "tenders": [{"method": "cash", "currency_code": "USD", "amount": "50.00"}],
                    "order_type": "takeaway",
                })

        call(client, "PATCH", "/auth/me/preferences", token=token, json={"preferences": {"setup_journey_dismissed": True}})
        print(json.dumps({"email": EMAIL, "password": PASSWORD, "store_id": store_id, "milk_id": milk["id"]}, indent=2))


if __name__ == "__main__":
    main()
