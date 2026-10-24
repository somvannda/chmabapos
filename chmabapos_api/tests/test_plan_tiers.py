"""The paid tiers gate the surface the pricing page promises.

Free is the single-counter core; Starter is the operating surface (including the
vertical depth: combos, serials, batches); Pro adds scale and governance. These
tests pin the boundary from the outside, so a capability that stops being
enforced - or starts being enforced on the wrong tier - fails here.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup

FREE_FEATURES = {"held_orders", "inventory_management", "khqr_payments", "multi_currency"}


async def _status(client: AsyncClient, path: str, headers: dict) -> int:
    return (await client.get(path, headers=headers)).status_code


@pytest.mark.asyncio
async def test_free_plan_is_the_single_counter_core() -> None:
    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Tier Free Co", "Main", plan="free")
            email, company_id = ctx["email"], ctx["company_id"]
            workspace = (await client.get("/api/v1/workspaces/current", headers=ctx["headers"])).json()
            assert set(workspace["plan_features"]) == FREE_FEATURES

            # Commerce and vertical depth are Starter.
            assert await _status(client, "/api/v1/combos", ctx["headers"]) == 403
            assert await _status(client, "/api/v1/serials", ctx["headers"]) == 403
            assert await _status(client, "/api/v1/inventory/expiring-batches", ctx["store_headers"]) == 403
            # Multi-store reporting is Pro.
            assert await _status(client, "/api/v1/reports/consolidated", ctx["headers"]) == 403
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_starter_includes_operations_but_not_scale() -> None:
    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Tier Starter Co", "Main", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]

            assert await _status(client, "/api/v1/combos", ctx["headers"]) == 200
            assert await _status(client, "/api/v1/serials", ctx["headers"]) == 200
            assert await _status(client, "/api/v1/inventory/expiring-batches", ctx["store_headers"]) == 200
            assert await _status(client, "/api/v1/trade-ins", ctx["store_headers"]) == 200

            # Custom roles and consolidated reporting are Pro.
            assert await _status(client, "/api/v1/reports/consolidated", ctx["headers"]) == 403
            roles = (await client.get("/api/v1/roles", headers=ctx["headers"])).json()
            manager = next(role for role in roles if role["key"] == "manager")
            patched = await client.patch(
                f"/api/v1/roles/{manager['id']}",
                headers=ctx["headers"],
                json={"permissions": ["sales.create"]},
            )
            assert patched.status_code == 403
    finally:
        await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_pro_includes_scale_and_governance() -> None:
    email = None
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Tier Pro Co", "Main", plan="pro")
            email, company_id = ctx["email"], ctx["company_id"]

            assert await _status(client, "/api/v1/reports/consolidated", ctx["headers"]) == 200
            roles = (await client.get("/api/v1/roles", headers=ctx["headers"])).json()
            manager = next(role for role in roles if role["key"] == "manager")
            patched = await client.patch(
                f"/api/v1/roles/{manager['id']}",
                headers=ctx["headers"],
                json={"permissions": ["sales.create"]},
            )
            assert patched.status_code == 200, patched.text
    finally:
        await cleanup_company(company_id, [email] if email else [])
