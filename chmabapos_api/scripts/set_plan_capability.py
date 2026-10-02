"""Enable or disable a plan capability from the command line.

Ops helper for adjusting a plan's capability map deterministically — e.g.
granting ``table_management`` back to the Starter plan after it was made
Pro-only — instead of hand-editing the database. Mirrors the platform-admin
plan editor.

Usage::

    python chmabapos_api/scripts/set_plan_capability.py --plan starter --capability table_management
    python chmabapos_api/scripts/set_plan_capability.py --plan starter --capability table_management --off
"""
import argparse
import asyncio
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

from app.db import SessionLocal  # noqa: E402
from app.features import FEATURE_CATALOG  # noqa: E402
from app.models import Plan  # noqa: E402


async def run(plan_code: str, capability: str, enabled: bool) -> None:
    if capability not in FEATURE_CATALOG:
        raise SystemExit(f"Unknown capability '{capability}'. Known: {', '.join(sorted(FEATURE_CATALOG))}")
    async with SessionLocal() as db:
        plan = await db.get(Plan, plan_code)
        if not plan:
            raise SystemExit(f"No plan with code '{plan_code}'")
        capabilities = dict(plan.capabilities or {})
        capabilities[capability] = enabled
        plan.capabilities = capabilities
        await db.commit()
        print(f"{plan.code}: {capability} = {enabled}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enable or disable a plan capability.")
    parser.add_argument("--plan", required=True, help="Plan code, e.g. starter or pro")
    parser.add_argument("--capability", required=True, help="Capability key, e.g. table_management")
    parser.add_argument("--off", action="store_true", help="Disable the capability (default: enable it)")
    args = parser.parse_args()
    asyncio.run(run(args.plan, args.capability, not args.off))


if __name__ == "__main__":
    main()
