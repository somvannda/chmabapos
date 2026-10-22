"""Plan-editor input validation and protected built-ins."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.schemas import AdminPlanCreateRequest
from tests.test_admin_subscription_management import _admin_headers, _cleanup, _free_workspace, _promote_super


def test_plan_code_is_normalized_and_capabilities_are_known() -> None:
    request = AdminPlanCreateRequest(code=" Custom-Plan ", name="Custom", monthly_price=10)
    assert request.code == "custom-plan"

    with pytest.raises(ValidationError):
        AdminPlanCreateRequest(code="bad code", name="Custom")
    with pytest.raises(ValidationError):
        AdminPlanCreateRequest(code="custom", name="Custom", capabilities={"not_a_feature": True})


@pytest.mark.asyncio
async def test_free_plan_cannot_be_deactivated_and_edits_are_audited() -> None:
    email = f"admin-plan-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    plan_code = f"custom-{uuid.uuid4().hex[:6]}"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            workspace = await _free_workspace(client, email)
            company_id = workspace["company"]["id"]
        await _promote_super(email)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin = await _admin_headers(client, email)

            protected = await client.patch("/api/v1/admin/plans/free", headers=admin, json={"is_active": False})
            assert protected.status_code == 400, protected.text

            created = await client.post(
                "/api/v1/admin/plans",
                headers=admin,
                json={"code": plan_code, "name": "Custom plan", "monthly_price": 10, "max_stores": 2, "max_members": 2},
            )
            assert created.status_code == 201, created.text

            updated = await client.patch(
                f"/api/v1/admin/plans/{plan_code}",
                headers=admin,
                json={"max_stores": 3, "capabilities": {"inventory_management": True}},
            )
            assert updated.status_code == 200, updated.text

        async with SessionLocal() as db:
            details = await db.scalar(
                text(
                    "SELECT details FROM audit_logs WHERE action = 'admin.plan_updated' "
                    "AND details->>'code' = :code ORDER BY created_at DESC LIMIT 1"
                ),
                {"code": plan_code},
            )
            assert details["max_stores"] == 3
            assert details["previous"]["max_stores"] == 2
    finally:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM audit_logs WHERE details->>'code' = :code"), {"code": plan_code})
            await db.execute(text("DELETE FROM plans WHERE code = :code"), {"code": plan_code})
            await db.commit()
        await _cleanup(email, company_id)
