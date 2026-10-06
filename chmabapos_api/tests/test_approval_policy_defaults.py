"""An enabled approval policy missing an action must not silently fall open."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import load_approval_policy
from app.db import SessionLocal
from app.main import app
from app.models import Company
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_missing_approval_rule_falls_back_to_the_default() -> None:
    company_id = None
    email = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Approval Defaults Store", "Main", plan="starter", email_prefix="appr-default")
            email, company_id = ctx["email"], ctx["company_id"]

            # Store an enabled policy that omits the refund rule (what an older
            # client would have written); it must not disable refund gating.
            async with SessionLocal() as db:
                company = await db.get(Company, uuid.UUID(company_id))
                settings = dict(company.settings or {})
                settings["approval_policy"] = {
                    "enabled": True,
                    "maker_checker": True,
                    "expiry_minutes": 60,
                    "notify_in_app": True,
                    "notify_telegram": False,
                    "rules": {"discount": {"mode": "off", "threshold": None, "approvers": ["owner"]}},
                }
                company.settings = settings
                await db.commit()

            async with SessionLocal() as db:
                policy = await load_approval_policy(db, uuid.UUID(company_id))
            assert policy.enabled
            assert policy.rules.get("refund") is not None
            assert policy.rules["refund"].mode == "review"
            # The explicitly-provided action is preserved as-is.
            assert policy.rules["discount"].mode == "off"
    finally:
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
