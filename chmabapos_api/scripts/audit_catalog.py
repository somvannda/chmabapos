#!/usr/bin/env python3
"""Read-only catalogue audit for a single company (tenant).

Finds likely data-entry problems in products, variants, serials, suppliers and
stock balances for ONE company. It is deliberately read-only: the database
session is put into read-only mode before the first query and every statement
is a SELECT.

Configuration is taken from the environment so it can be piped into a running
container without arguments:

    AUDIT_EMAIL=somvannda@gmail.com python scripts/audit_catalog.py

* ``AUDIT_EMAIL``       owner / member email used to resolve the company.
* ``AUDIT_COMPANY_ID``  optional explicit company id (skips email lookup).
* ``SYNC_DATABASE_URL`` or ``DATABASE_URL``  database connection string.

The result is a single JSON document on stdout.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

SAMPLE_LIMIT = 25


def conninfo() -> str:
    url = os.environ.get("SYNC_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    if not url:
        raise SystemExit("Set SYNC_DATABASE_URL or DATABASE_URL")
    # libpq does not understand SQLAlchemy's "+driver" marker.
    return (
        url.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
    )


def norm(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).lower()


def canon_attrs(attrs: Any) -> str:
    """Order-independent, case-insensitive signature of a variant's attributes."""
    if not isinstance(attrs, dict):
        return ""
    pairs = []
    for key, value in attrs.items():
        nk, nv = norm(key), norm(value)
        if nk or nv:
            pairs.append(f"{nk}={nv}")
    return "|".join(sorted(pairs))


def dec(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def resolve_company(cur, email: str | None, company_id: str | None) -> dict:
    if company_id:
        row = cur.execute(
            "SELECT id, name FROM companies WHERE id = %s", (company_id,)
        ).fetchone()
        if not row:
            raise SystemExit(f"No company with id {company_id}")
        return {"id": str(row["id"]), "name": row["name"], "matched_by": "company_id"}

    if not email:
        raise SystemExit("Set AUDIT_EMAIL (or AUDIT_COMPANY_ID)")

    user = cur.execute(
        "SELECT id, email, full_name FROM users WHERE lower(email) = lower(%s)",
        (email,),
    ).fetchone()
    if not user:
        raise SystemExit(f"No user with email {email}")

    rows = cur.execute(
        """
        SELECT m.company_id, m.role, m.status, c.name AS company_name
        FROM memberships m
        JOIN companies c ON c.id = m.company_id
        WHERE m.user_id = %s
        ORDER BY (m.role = 'owner') DESC, c.name
        """,
        (user["id"],),
    ).fetchall()
    if not rows:
        raise SystemExit(f"{email} is not a member of any company")

    owners = [r for r in rows if r["role"] == "owner"]
    choice = owners[0] if len(owners) == 1 else (rows[0] if len(rows) == 1 else None)
    if choice is None:
        listing = [{"company_id": str(r["company_id"]), "role": r["role"], "company": r["company_name"]} for r in rows]
        raise SystemExit(
            "Multiple companies for this user; re-run with AUDIT_COMPANY_ID set to one of:\n"
            + json.dumps(listing, indent=2)
        )
    return {
        "id": str(choice["company_id"]),
        "name": choice["company_name"],
        "matched_by": f"{email} ({choice['role']})",
    }


def fetch(cur, company_id: str) -> dict[str, list[dict]]:
    return {
        "stores": cur.execute(
            "SELECT id, name FROM stores WHERE company_id = %s ORDER BY name",
            (company_id,),
        ).fetchall(),
        "categories": cur.execute(
            "SELECT id, name, is_active FROM categories WHERE company_id = %s ORDER BY name",
            (company_id,),
        ).fetchall(),
        "products": cur.execute(
            """
            SELECT id, sku, name, category_id, price, cost_price, track_inventory,
                   track_serials, is_active, brand, barcode, attributes
            FROM products WHERE company_id = %s ORDER BY name
            """,
            (company_id,),
        ).fetchall(),
        "variants": cur.execute(
            """
            SELECT v.id, v.product_id, v.sku, v.barcode, v.name, v.price, v.cost_price,
                   v.attributes, v.is_active, v.position
            FROM product_variants v
            JOIN products p ON p.id = v.product_id
            WHERE p.company_id = %s
            ORDER BY p.name, v.position, v.name
            """,
            (company_id,),
        ).fetchall(),
        "product_balances": cur.execute(
            """
            SELECT b.store_id, b.product_id, b.on_hand, b.reorder_point
            FROM inventory_balances b
            JOIN stores s ON s.id = b.store_id
            WHERE s.company_id = %s
            """,
            (company_id,),
        ).fetchall(),
        "variant_balances": cur.execute(
            """
            SELECT b.store_id, b.variant_id, b.on_hand, b.reorder_point
            FROM variant_inventory_balances b
            JOIN stores s ON s.id = b.store_id
            WHERE s.company_id = %s
            """,
            (company_id,),
        ).fetchall(),
        "serials": cur.execute(
            """
            SELECT id, product_id, variant_id, store_id, serial_number, status,
                   cost_price, supplier_id, sold_at, condition_grade,
                   battery_health, imei
            FROM product_serials WHERE company_id = %s
            """,
            (company_id,),
        ).fetchall(),
        "suppliers": cur.execute(
            "SELECT id, name, is_active FROM suppliers WHERE company_id = %s ORDER BY name",
            (company_id,),
        ).fetchall(),
    }


def sample(rows: list[dict], fields: list[str]) -> list[dict]:
    out = []
    for row in rows[:SAMPLE_LIMIT]:
        out.append({f: (str(row[f]) if row.get(f) is not None else None) for f in fields})
    return out


def check(label: str, severity: str, rows: list[dict], fields: list[str], note: str = "") -> dict:
    return {
        "check": label,
        "severity": severity,
        "count": len(rows),
        "note": note,
        "samples": sample(rows, fields),
    }


def build_checks(data: dict[str, list[dict]]) -> list[dict]:
    products = {p["id"]: p for p in data["products"]}
    variants = data["variants"]
    variants_by_product: dict[Any, list[dict]] = defaultdict(list)
    for v in variants:
        variants_by_product[v["product_id"]].append(v)

    serials = data["serials"]
    serials_by_product: dict[Any, list[dict]] = defaultdict(list)
    for s in serials:
        serials_by_product[s["product_id"]].append(s)

    balances_by_product = {b["product_id"]: b for b in data["product_balances"]}
    balances_by_variant = {b["variant_id"]: b for b in data["variant_balances"]}

    checks: list[dict] = []

    # --- Duplicate variant specs (the supplier-per-variant trap) -------------
    dup_specs: dict[tuple, list[dict]] = defaultdict(list)
    for v in variants:
        dup_specs[(v["product_id"], canon_attrs(v["attributes"]), norm(v["name"]))].append(v)
    dup_spec_rows = []
    for (product_id, signature, name), group in dup_specs.items():
        if len(group) > 1 and signature:
            dup_spec_rows.append({
                "product": products.get(product_id, {}).get("name"),
                "product_sku": products.get(product_id, {}).get("sku"),
                "variant_name": name,
                "spec": signature,
                "variant_count": len(group),
                "skus": ", ".join(str(g["sku"]) for g in group),
                "costs": ", ".join(str(dec(g["cost_price"])) for g in group),
            })
    checks.append(check(
        "duplicate_variant_specs", "high", dup_spec_rows,
        ["product", "product_sku", "variant_name", "spec", "variant_count", "skus", "costs"],
        "Same product + identical attributes + same variant name. Usually the same "
        "sellable item duplicated to represent different suppliers/costs.",
    ))

    # --- Duplicate variant names within a product ---------------------------
    dup_names: dict[tuple, list[dict]] = defaultdict(list)
    for v in variants:
        dup_names[(v["product_id"], norm(v["name"]))].append(v)
    dup_name_rows = [
        {
            "product": products.get(pid, {}).get("name"),
            "variant_name": name,
            "variant_count": len(group),
            "skus": ", ".join(str(g["sku"]) for g in group),
        }
        for (pid, name), group in dup_names.items()
        if len(group) > 1 and name
    ]
    checks.append(check(
        "duplicate_variant_names", "medium", dup_name_rows,
        ["product", "variant_name", "variant_count", "skus"],
        "Variants sharing a name within one product; POS/receipts will look ambiguous.",
    ))

    # --- Duplicate product names / SKUs -------------------------------------
    dup_products: dict[str, list[dict]] = defaultdict(list)
    for p in data["products"]:
        dup_products[norm(p["name"])].append(p)
    dup_product_rows = [
        {
            "product_name": group[0]["name"],
            "product_count": len(group),
            "skus": ", ".join(str(g["sku"]) for g in group),
            "variant_counts": ", ".join(str(len(variants_by_product.get(g["id"], []))) for g in group),
        }
        for name, group in dup_products.items()
        if len(group) > 1 and name
    ]
    checks.append(check(
        "duplicate_product_names", "medium", dup_product_rows,
        ["product_name", "product_count", "skus", "variant_counts"],
        "Several products with the same normalised name; confirm they are genuinely distinct.",
    ))

    # --- Attribute key / value casing drift ---------------------------------
    key_variants: dict[str, set] = defaultdict(set)
    for v in variants:
        attrs = v["attributes"] if isinstance(v["attributes"], dict) else {}
        for key in attrs:
            key_variants[norm(key)].add(str(key))
    key_rows = [
        {"attribute": k, "spellings": ", ".join(sorted(v))}
        for k, v in key_variants.items() if len(v) > 1 and k
    ]
    # value spelling drift, keyed by attribute + normalised value
    val_groups: dict[tuple, set] = defaultdict(set)
    for v in variants:
        attrs = v["attributes"] if isinstance(v["attributes"], dict) else {}
        for key, value in attrs.items():
            val_groups[(norm(key), norm(value))].add(str(value))
    value_rows = [
        {"attribute": k, "value_count": len(v), "spellings": ", ".join(sorted(v))}
        for (k, _), v in val_groups.items() if len(v) > 1
    ]
    checks.append(check(
        "attribute_key_spelling_drift", "medium", key_rows,
        ["attribute", "spellings"],
        "The same attribute key written with different casing/spacing; splitting edits.",
    ))
    checks.append(check(
        "attribute_value_spelling_drift", "low", value_rows,
        ["attribute", "value_count", "spellings"],
        "Values that differ only by case/punctuation (e.g. 'Space Gray' vs 'space gray').",
    ))

    # --- Variant pricing problems -------------------------------------------
    variant_price_rows = []
    for v in variants:
        price, cost = v["price"], v["cost_price"]
        problems = []
        if price is None:
            problems.append("missing_price")
        elif float(price) <= 0:
            problems.append("price_not_positive")
        if cost is None:
            problems.append("missing_cost")
        if price is not None and cost is not None and float(price) < float(cost):
            problems.append("price_below_cost")
        if problems:
            variant_price_rows.append({
                "product": products.get(v["product_id"], {}).get("name"),
                "variant": v["name"],
                "sku": v["sku"],
                "price": dec(price),
                "cost": dec(cost),
                "issue": ", ".join(problems),
            })
    checks.append(check(
        "variant_pricing", "high", variant_price_rows,
        ["product", "variant", "sku", "price", "cost", "issue"],
        "Variant price/cost missing, zero, or below cost.",
    ))

    # --- Product pricing problems (products without variants) ---------------
    product_price_rows = []
    for p in data["products"]:
        if variants_by_product.get(p["id"]):
            continue  # priced per variant
        price, cost = p["price"], p["cost_price"]
        problems = []
        if price is None or float(price) <= 0:
            problems.append("price_not_positive")
        if cost is None:
            problems.append("missing_cost")
        if price is not None and cost is not None and float(price) < float(cost):
            problems.append("price_below_cost")
        if problems:
            product_price_rows.append({
                "product": p["name"], "sku": p["sku"], "price": dec(price),
                "cost": dec(cost), "issue": ", ".join(problems),
            })
    checks.append(check(
        "product_pricing", "high", product_price_rows,
        ["product", "sku", "price", "cost", "issue"],
        "Products without variants whose price/cost is missing or below cost.",
    ))

    # --- Serials missing supplier / cost ------------------------------------
    serial_no_supplier = []
    for s in serials:
        if s["status"] == "in_stock" and s["supplier_id"] is None:
            serial_no_supplier.append({
                "product": products.get(s["product_id"], {}).get("name"),
                "serial": s["serial_number"], "variant_id": str(s["variant_id"]) if s["variant_id"] else None,
            })
    checks.append(check(
        "in_stock_serials_missing_supplier", "high", serial_no_supplier,
        ["product", "serial", "variant_id"],
        "In-stock units with no supplier recorded; the whole point of per-unit supplier tracking.",
    ))

    serial_no_cost = []
    for s in serials:
        if s["status"] in ("in_stock", "sold") and s["cost_price"] is None:
            serial_no_cost.append({
                "product": products.get(s["product_id"], {}).get("name"),
                "serial": s["serial_number"], "status": s["status"],
            })
    checks.append(check(
        "serials_missing_cost", "high", serial_no_cost,
        ["product", "serial", "status"],
        "Units without a cost basis; COGS/margin will be wrong for these.",
    ))

    sold_no_cost = [
        {"product": products.get(s["product_id"], {}).get("name"), "serial": s["serial_number"], "sold_at": str(s["sold_at"])}
        for s in serials if s["status"] == "sold" and s["cost_price"] is None
    ]
    checks.append(check(
        "sold_serials_missing_cost", "high", sold_no_cost,
        ["product", "serial", "sold_at"],
        "Already-sold units with zero frozen cost; margin reports understate cost.",
    ))

    # --- Serial ↔ variant mapping -------------------------------------------
    mismatch = []
    for s in serials:
        product = products.get(s["product_id"])
        if not product:
            continue
        product_variants = variants_by_product.get(s["product_id"], [])
        if product_variants and s["variant_id"] is None and s["status"] == "in_stock":
            mismatch.append({
                "product": product["name"], "serial": s["serial_number"],
                "issue": "product_has_variants_but_serial_has_none",
            })
        elif s["variant_id"] is not None:
            if s["variant_id"] not in {v["id"] for v in product_variants}:
                mismatch.append({
                    "product": product["name"], "serial": s["serial_number"],
                    "issue": "serial_variant_not_in_product",
                })
    checks.append(check(
        "serial_variant_mismatch", "high", mismatch,
        ["product", "serial", "issue"],
        "Units not attached to the right variant (or missing a variant).",
    ))

    # --- Stock balance vs serial count --------------------------------------
    balance_issues = []
    for p in data["products"]:
        if not p["track_serials"]:
            continue
        product_variants = variants_by_product.get(p["id"], [])
        live = [s for s in serials_by_product.get(p["id"], []) if s["status"] == "in_stock" and s["store_id"]]
        if product_variants:
            by_variant: dict[tuple, int] = defaultdict(int)
            for s in live:
                by_variant[(s["store_id"], s["variant_id"])] += 1
            for v in product_variants:
                expected = sum(c for (st, vid), c in by_variant.items() if vid == v["id"])
                actual = float(balances_by_variant.get(v["id"], {}).get("on_hand", 0) or 0)
                if expected != actual:
                    balance_issues.append({
                        "product": p["name"], "variant": v["name"],
                        "expected_serial_units": expected, "balance_on_hand": actual,
                    })
        else:
            expected = len(live)
            actual = float(balances_by_product.get(p["id"], {}).get("on_hand", 0) or 0)
            if expected != actual:
                balance_issues.append({
                    "product": p["name"], "variant": None,
                    "expected_serial_units": expected, "balance_on_hand": actual,
                })
    checks.append(check(
        "stock_balance_vs_serials", "high", balance_issues,
        ["product", "variant", "expected_serial_units", "balance_on_hand"],
        "On-hand balance disagrees with the number of in-stock serial units.",
    ))

    # --- Inactive variants holding stock ------------------------------------
    inactive_with_stock = []
    for v in variants:
        if not v["is_active"] and float(balances_by_variant.get(v["id"], {}).get("on_hand", 0) or 0) > 0:
            inactive_with_stock.append({
                "product": products.get(v["product_id"], {}).get("name"),
                "variant": v["name"], "on_hand": float(balances_by_variant[v["id"]]["on_hand"]),
            })
    checks.append(check(
        "inactive_variant_with_stock", "medium", inactive_with_stock,
        ["product", "variant", "on_hand"],
        "Deactivated variants still showing stock; hide them only when empty.",
    ))

    # --- Negative balances --------------------------------------------------
    negative = [
        {"product": products.get(b["product_id"], {}).get("name"), "on_hand": float(b["on_hand"])}
        for b in data["product_balances"] if b["on_hand"] is not None and float(b["on_hand"]) < 0
    ]
    negative += [
        {"product": products.get(next((v["product_id"] for v in variants if v["id"] == b["variant_id"]), None), {}).get("name"),
         "on_hand": float(b["on_hand"])}
        for b in data["variant_balances"] if b["on_hand"] is not None and float(b["on_hand"]) < 0
    ]
    checks.append(check(
        "negative_stock", "high", negative, ["product", "on_hand"],
        "Negative balances indicate a missing receipt or a bad adjustment.",
    ))

    # --- Duplicate barcodes -------------------------------------------------
    barcode_map: dict[str, list] = defaultdict(list)
    for p in data["products"]:
        if p["barcode"]:
            barcode_map[str(p["barcode"])].append(f"product:{p['name']}")
    for v in variants:
        if v["barcode"]:
            barcode_map[str(v["barcode"])].append(f"variant:{v['name']}")
    dup_barcodes = [
        {"barcode": bc, "uses": ", ".join(items), "count": len(items)}
        for bc, items in barcode_map.items() if len(items) > 1
    ]
    checks.append(check(
        "duplicate_barcodes", "medium", dup_barcodes, ["barcode", "uses", "count"],
        "A barcode resolving to more than one item makes scanning ambiguous.",
    ))

    # --- Missing category (informational) -----------------------------------
    no_category = [
        {"product": p["name"], "sku": p["sku"]}
        for p in data["products"] if p["category_id"] is None
    ]
    checks.append(check(
        "product_without_category", "low", no_category, ["product", "sku"],
        "Products not filed under a category; cosmetic but breaks category reports.",
    ))

    # --- Component products of inactive parents -----------------------------
    orphan_variants = [
        {"product": products.get(v["product_id"], {}).get("name"), "variant": v["name"], "sku": v["sku"]}
        for v in variants if not products.get(v["product_id"], {}).get("is_active", True)
    ]
    checks.append(check(
        "variant_under_inactive_product", "low", orphan_variants,
        ["product", "variant", "sku"],
        "Variants belonging to a deactivated product.",
    ))

    return checks


def main() -> None:
    email = os.environ.get("AUDIT_EMAIL", "somvannda@gmail.com")
    company_id = os.environ.get("AUDIT_COMPANY_ID") or None

    with psycopg.connect(conninfo(), row_factory=dict_row) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            company = resolve_company(cur, email, company_id)
            data = fetch(cur, company["id"])

    checks = build_checks(data)
    # A machine-readable dump of the catalogue so an operator can build a
    # fill-in spreadsheet (serials with their product/variant/supplier names).
    product_by_id = {p["id"]: p for p in data["products"]}
    variant_by_id = {v["id"]: v for v in data["variants"]}
    supplier_by_id = {s["id"]: s for s in data["suppliers"]}
    export_serials = []
    for serial in data["serials"]:
        product = product_by_id.get(serial["product_id"], {})
        variant = variant_by_id.get(serial["variant_id"]) if serial["variant_id"] else None
        supplier = supplier_by_id.get(serial["supplier_id"]) if serial["supplier_id"] else None
        export_serials.append({
            "serial_number": serial["serial_number"],
            "imei": serial.get("imei"),
            "product": product.get("name"),
            "product_sku": product.get("sku"),
            "variant": variant.get("name") if variant else None,
            "variant_sku": variant.get("sku") if variant else None,
            "status": serial["status"],
            "supplier": supplier.get("name") if supplier else None,
            "cost_price": dec(serial["cost_price"]),
            "condition_grade": serial.get("condition_grade"),
            "battery_health": serial.get("battery_health"),
            "sold_at": str(serial["sold_at"]) if serial["sold_at"] else None,
        })
    export_variants = [
        {
            "id": str(variant["id"]),
            "product": product_by_id.get(variant["product_id"], {}).get("name"),
            "name": variant["name"],
            "sku": variant["sku"],
            "is_active": variant["is_active"],
            "price": dec(variant["price"]),
            "cost_price": dec(variant["cost_price"]),
        }
        for variant in data["variants"]
    ]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "company": company,
        "row_counts": {
            "stores": len(data["stores"]),
            "categories": len(data["categories"]),
            "products": len(data["products"]),
            "variants": len(data["variants"]),
            "serials": len(data["serials"]),
            "suppliers": len(data["suppliers"]),
        },
        "issue_total": sum(c["count"] for c in checks),
        "checks": checks,
        "export": {
            "suppliers": [{"id": str(s["id"]), "name": s["name"], "is_active": s["is_active"]} for s in data["suppliers"]],
            "products": [
                {"id": str(p["id"]), "name": p["name"], "sku": p["sku"], "price": dec(p["price"]), "cost_price": dec(p["cost_price"]), "is_active": p["is_active"]}
                for p in data["products"]
            ],
            "variants": export_variants,
            "serials": export_serials,
        },
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
