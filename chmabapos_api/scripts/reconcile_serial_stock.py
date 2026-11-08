#!/usr/bin/env python3
"""Reconcile serial-tracked stock balances with the serial list.

For a product that tracks serials, the serial rows are the truth: one
``in_stock`` unit per physical unit on the shelf. Balances should already match,
but an opening stock or a manual balance edit made before those writes were
guarded can leave a product showing more (or fewer) units than its serial list.

This script prints every disagreement and, with ``--apply``, rewrites the
balance to the serial count and records an auditable ``manual_adjustment``
movement for the difference. It is dry-run by default.

    # See every drift for one company
    RECONCILE_COMPANY_ID=<uuid> python chmabapos_api/scripts/reconcile_serial_stock.py

    # Apply the corrections
    RECONCILE_COMPANY_ID=<uuid> python chmabapos_api/scripts/reconcile_serial_stock.py --apply

Configuration is read from ``SYNC_DATABASE_URL`` or ``DATABASE_URL``. If
``RECONCILE_COMPANY_ID`` is unset, every company is inspected (read-only unless
``--apply`` is passed).

Two things the script will *not* do silently:

* Units with no serial number (an "anonymous" balance) are reported but the
  script reduces the balance rather than inventing serial numbers. If those
  units physically exist, add their serials first, then run this script.
* In-stock serials with no store (the unattributed company pool) are reported
  separately. They belong to no shelf, so they cannot be reconciled into one.
"""
from __future__ import annotations

import argparse
import os
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row


def conninfo() -> str:
    url = os.environ.get("SYNC_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    if not url:
        raise SystemExit("Set SYNC_DATABASE_URL or DATABASE_URL")
    return (
        url.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
    )


@dataclass
class Fix:
    """One balance correction."""

    store_id: Any
    product_id: Any
    product_name: str
    variant_id: Any | None
    variant_name: str | None
    expected: Decimal
    actual: Decimal
    row_exists: bool

    @property
    def difference(self) -> Decimal:
        return self.expected - self.actual


def fetch(cur: psycopg.Cursor, company_id: str | None) -> dict[str, list[dict]]:
    where = "WHERE p.company_id = %s" if company_id else ""
    params: tuple = (company_id,) if company_id else ()
    return {
        "products": cur.execute(
            f"SELECT id, company_id, name, sku, track_serials FROM products p {where} AND p.track_serials = TRUE"
            if company_id
            else "SELECT id, company_id, name, sku, track_serials FROM products p WHERE p.track_serials = TRUE",
            params,
        ).fetchall(),
        "variants": cur.execute(
            "SELECT v.id, v.product_id, v.name, v.sku FROM product_variants v "
            "JOIN products p ON p.id = v.product_id "
            + (f"WHERE p.company_id = %s AND p.track_serials = TRUE" if company_id else "WHERE p.track_serials = TRUE"),
            params,
        ).fetchall(),
        "product_balances": cur.execute(
            "SELECT b.store_id, b.product_id, b.on_hand FROM inventory_balances b "
            "JOIN products p ON p.id = b.product_id "
            + (f"WHERE p.company_id = %s AND p.track_serials = TRUE" if company_id else "WHERE p.track_serials = TRUE"),
            params,
        ).fetchall(),
        "variant_balances": cur.execute(
            "SELECT b.store_id, b.variant_id, b.on_hand FROM variant_inventory_balances b "
            "JOIN product_variants v ON v.id = b.variant_id "
            "JOIN products p ON p.id = v.product_id "
            + (f"WHERE p.company_id = %s AND p.track_serials = TRUE" if company_id else "WHERE p.track_serials = TRUE"),
            params,
        ).fetchall(),
        "serials": cur.execute(
            "SELECT s.id, s.product_id, s.variant_id, s.store_id, s.serial_number, s.status FROM product_serials s "
            "JOIN products p ON p.id = s.product_id "
            + (f"WHERE p.company_id = %s AND p.track_serials = TRUE" if company_id else "WHERE p.track_serials = TRUE"),
            params,
        ).fetchall(),
    }


def build_fixes(data: dict[str, list[dict]]) -> tuple[list[Fix], list[dict], list[dict]]:
    products = {p["id"]: p for p in data["products"]}
    variants_by_product: dict[Any, list[dict]] = defaultdict(list)
    variant_names: dict[Any, str] = {}
    for variant in data["variants"]:
        variants_by_product[variant["product_id"]].append(variant)
        variant_names[variant["id"]] = variant["name"]

    # In-stock units per (product, variant, store). Null-store units are the
    # unattributed pool and are reported separately.
    expected_variant: dict[tuple, int] = defaultdict(int)
    expected_product: dict[tuple, int] = defaultdict(int)
    unattributed: list[dict] = []
    for serial in data["serials"]:
        if serial["status"] != "in_stock":
            continue
        if serial["store_id"] is None:
            unattributed.append(serial)
            continue
        product = products.get(serial["product_id"])
        if not product:
            continue
        if variants_by_product.get(serial["product_id"]):
            if serial["variant_id"] is None:
                unattributed.append(serial)
                continue
            expected_variant[(serial["store_id"], serial["variant_id"])] += 1
        else:
            expected_product[(serial["store_id"], serial["product_id"])] += 1

    actual_variant = {(row["store_id"], row["variant_id"]): Decimal(str(row["on_hand"] or 0)) for row in data["variant_balances"]}
    actual_product = {(row["store_id"], row["product_id"]): Decimal(str(row["on_hand"] or 0)) for row in data["product_balances"]}

    fixes: list[Fix] = []
    for product_id, variants in variants_by_product.items():
        product = products.get(product_id)
        if not product:
            continue
        for variant in variants:
            keys = {key for key in list(expected_variant) + list(actual_variant) if key[1] == variant["id"]}
            for store_id, variant_id in keys:
                expected = Decimal(expected_variant.get((store_id, variant_id), 0))
                actual = actual_variant.get((store_id, variant_id), Decimal("0"))
                if expected != actual:
                    fixes.append(Fix(store_id, product_id, product["name"], variant_id, variant_names.get(variant_id), expected, actual, (store_id, variant_id) in actual_variant))

    for product_id, product in products.items():
        if variants_by_product.get(product_id):
            continue
        keys = {key for key in list(expected_product) + list(actual_product) if key[1] == product_id}
        for store_id, pid in keys:
            expected = Decimal(expected_product.get((store_id, pid), 0))
            actual = actual_product.get((store_id, pid), Decimal("0"))
            if expected != actual:
                fixes.append(Fix(store_id, product_id, product["name"], None, None, expected, actual, (store_id, pid) in actual_product))

    return fixes, unattributed, data["serials"]


def apply_fix(cur: psycopg.Cursor, fix: Fix) -> None:
    if fix.variant_id:
        if fix.row_exists:
            cur.execute(
                "UPDATE variant_inventory_balances SET on_hand = %s, updated_at = now() WHERE store_id = %s AND variant_id = %s",
                (fix.expected, fix.store_id, fix.variant_id),
            )
        else:
            cur.execute(
                "INSERT INTO variant_inventory_balances (store_id, variant_id, on_hand, reorder_point, updated_at) "
                "VALUES (%s, %s, %s, 10, now())",
                (fix.store_id, fix.variant_id, fix.expected),
            )
    else:
        if fix.row_exists:
            cur.execute(
                "UPDATE inventory_balances SET on_hand = %s, updated_at = now() WHERE store_id = %s AND product_id = %s",
                (fix.expected, fix.store_id, fix.product_id),
            )
        else:
            cur.execute(
                "INSERT INTO inventory_balances (store_id, product_id, on_hand, reorder_point, updated_at) "
                "VALUES (%s, %s, %s, 10, now())",
                (fix.store_id, fix.product_id, fix.expected),
            )
    cur.execute(
        "INSERT INTO stock_movements (id, store_id, product_id, variant_id, quantity, movement_type, reason, created_at) "
        "VALUES (gen_random_uuid(), %s, %s, %s, %s, 'manual_adjustment', 'serial_reconciliation', now())",
        (fix.store_id, fix.product_id, fix.variant_id, fix.difference),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the corrections; default is a dry run")
    parser.add_argument("--company-id", default=os.environ.get("RECONCILE_COMPANY_ID") or None, help="limit to one company UUID")
    args = parser.parse_args()

    with psycopg.connect(conninfo(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            data = fetch(cur, args.company_id)
            fixes, unattributed, serials = build_fixes(data)
            if args.apply and fixes:
                for fix in fixes:
                    apply_fix(cur, fix)
        if args.apply:
            conn.commit()

    print(f"Inspected {len(data['products'])} serial-tracked product(s), {len(serials)} serial unit(s).")
    if not fixes:
        print("All serial-tracked balances already match their serial list.")
    else:
        print(f"{'Applying' if args.apply else 'Would apply'} {len(fixes)} correction(s):")
        for fix in fixes:
            label = fix.product_name + (f" · {fix.variant_name}" if fix.variant_name else "")
            print(f"  {label}: balance {fix.actual} -> {fix.expected} (delta {fix.difference:+})")
    if unattributed:
        print(f"{len(unattributed)} in-stock serial(s) are not attributable to one shelf and were left alone:")
        for serial in unattributed[:20]:
            print(f"  {serial['serial_number']} (product {serial['product_id']}, store {serial['store_id']})")
        if len(unattributed) > 20:
            print(f"  ... and {len(unattributed) - 20} more")
    if fixes and not args.apply:
        print("Re-run with --apply to write these corrections.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
