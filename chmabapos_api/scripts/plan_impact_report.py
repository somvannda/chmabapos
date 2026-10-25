"""Report which Free workspaces rely on a capability that now needs a paid plan.

Run this before announcing a plan change: it turns "some free users are
affected" into a number, and with ``--details`` into the list of accounts to
write to or to grant a transition period.

Read-only. It applies the same grace window as the entitlement resolver
(``settings.billing_grace_hours``), so a paid period that has just lapsed still
counts as paid here.

Usage::

    python chmabapos_api/scripts/plan_impact_report.py
    python chmabapos_api/scripts/plan_impact_report.py --details
    python chmabapos_api/scripts/plan_impact_report.py --json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402

# ``is_active`` on the company only: a paused store still belongs to a workspace.
SUMMARY_QUERY = text(
    """
    WITH in_force_paid AS (
        SELECT DISTINCT s.company_id
        FROM subscriptions s
        WHERE s.status = 'active'
          AND s.plan_code <> 'free'
          AND s.starts_at <= now()
          AND (s.ends_at IS NULL OR s.ends_at + (:grace * interval '1 hour') > now())
    ),
    free_companies AS (
        SELECT c.id, c.name
        FROM companies c
        WHERE c.is_active
          AND c.id NOT IN (SELECT company_id FROM in_force_paid)
    )
    SELECT
        (SELECT count(*) FROM free_companies) AS free_companies,
        (SELECT count(DISTINCT st.company_id) FROM stores st
          JOIN free_companies fc ON fc.id = st.company_id
         WHERE st.public_order_enabled) AS online_ordering,
        (SELECT count(DISTINCT c.company_id) FROM combos c
          JOIN free_companies fc ON fc.id = c.company_id) AS combos,
        (SELECT count(DISTINCT ps.company_id) FROM product_serials ps
          JOIN free_companies fc ON fc.id = ps.company_id) AS serials,
        (SELECT count(DISTINCT sx.company_id) FROM product_batches pb
          JOIN stores sx ON sx.id = pb.store_id
          JOIN free_companies fc ON fc.id = sx.company_id) AS batches,
        (SELECT count(DISTINCT company_id) FROM (
            SELECT st.company_id FROM stores st
              JOIN free_companies fc ON fc.id = st.company_id
             WHERE st.public_order_enabled
            UNION SELECT c.company_id FROM combos c
              JOIN free_companies fc ON fc.id = c.company_id
            UNION SELECT ps.company_id FROM product_serials ps
              JOIN free_companies fc ON fc.id = ps.company_id
            UNION SELECT sx.company_id FROM product_batches pb
              JOIN stores sx ON sx.id = pb.store_id
              JOIN free_companies fc ON fc.id = sx.company_id
        ) affected) AS any_capability
    """
)

DETAILS_QUERY = text(
    """
    WITH in_force_paid AS (
        SELECT DISTINCT s.company_id
        FROM subscriptions s
        WHERE s.status = 'active'
          AND s.plan_code <> 'free'
          AND s.starts_at <= now()
          AND (s.ends_at IS NULL OR s.ends_at + (:grace * interval '1 hour') > now())
    ),
    free_companies AS (
        SELECT c.id, c.name
        FROM companies c
        WHERE c.is_active
          AND c.id NOT IN (SELECT company_id FROM in_force_paid)
    )
    SELECT
        fc.id,
        fc.name,
        EXISTS (
            SELECT 1 FROM stores st
            WHERE st.company_id = fc.id AND st.public_order_enabled
        ) AS online_ordering,
        EXISTS (SELECT 1 FROM combos c WHERE c.company_id = fc.id) AS combos,
        EXISTS (SELECT 1 FROM product_serials ps WHERE ps.company_id = fc.id) AS serials,
        EXISTS (
            SELECT 1 FROM product_batches pb
            JOIN stores sx ON sx.id = pb.store_id
            WHERE sx.company_id = fc.id
        ) AS batches
    FROM free_companies fc
    ORDER BY fc.name
    """
)

LABELS = {
    "online_ordering": "Online ordering / QR menu",
    "combos": "Combos & meal deals",
    "serials": "Serials, warranty & trade-in",
    "batches": "Batches & expiry",
}


async def run(as_json: bool, details: bool) -> None:
    params = {"grace": settings.billing_grace_hours}
    async with SessionLocal() as db:
        summary = {
            key: int(value or 0)
            for key, value in (await db.execute(SUMMARY_QUERY, params)).mappings().one().items()
        }
        rows = []
        if details:
            rows = (await db.execute(DETAILS_QUERY, params)).mappings().all()

    if as_json:
        payload = dict(summary)
        if details:
            payload["companies"] = [
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "capabilities": [key for key in LABELS if row[key]],
                }
                for row in rows
            ]
        print(json.dumps(payload, indent=2))
        return

    print(f"Free workspaces: {summary['free_companies']}")
    print(f"Using at least one newly paid capability: {summary['any_capability']}")
    print("")
    print("Free workspaces still using a capability that now needs Starter:")
    for key, label in LABELS.items():
        print(f"  {label:<28} {summary[key]:>6}")

    if details:
        print("")
        print("Accounts to contact:")
        affected = [row for row in rows if any(row[key] for key in LABELS)]
        if not affected:
            print("  (none)")
        for row in affected:
            used = ", ".join(LABELS[key] for key in LABELS if row[key])
            print(f"  {row['name']}  [{row['id']}]  {used}")

    print("")
    print(
        "A transition period is one admin call per account:\n"
        '  POST /api/v1/admin/companies/<id>/subscription\n'
        '  {"action": "grant", "plan_code": "starter", "billing_cycle": "monthly",\n'
        '   "reason": "free-tier transition"}'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Report Free workspaces affected by the plan change.")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--details", action="store_true", help="list the affected workspaces")
    args = parser.parse_args()
    asyncio.run(run(args.json, args.details))


if __name__ == "__main__":
    main()
