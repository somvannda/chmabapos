"""Owner warnings when a workspace nears its plan limits."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
from app.services import quota_warnings
from app.services.quota_warnings import run_quota_warnings
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _warnings(owner_email: str | None) -> list[EmailSend]:
    if not owner_email:
        return []
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(EmailSend).where(EmailSend.recipient_email == owner_email, EmailSend.source == "quota_warning")
            )
        ).scalars().all()
        for row in rows:
            db.expunge(row)
        return rows


async def _cleanup(email: str | None, company_id: str | None) -> None:
    if email:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
            await db.commit()
    if company_id:
        await cleanup_company(company_id, [email] if email else [])


class _StubPlan:
    def __init__(self, *, code: str, name: str, max_stores: int, max_members: int) -> None:
        self.code = code
        self.name = name
        self.max_stores = max_stores
        self.max_members = max_members


class _StubEntitlement:
    def __init__(self, plan: _StubPlan) -> None:
        self.plan = plan


@pytest.mark.asyncio
async def test_quota_warning_skips_free_plan() -> None:
    """Free workspaces sit at their baseline limits and must not be nudged."""
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Free allows 1 store / 1 seat, so this workspace is already full.
            ctx = await register_and_setup(client, "Free Quota Store", "Main", plan="free", email_prefix="quota-free")
            email, company_id = ctx["email"], ctx["company_id"]

        async with SessionLocal() as db:
            await run_quota_warnings(db)

        assert await _warnings(email) == []
    finally:
        await _cleanup(email, company_id)


@pytest.mark.asyncio
async def test_quota_warning_emails_paid_owner_and_dedupes(monkeypatch) -> None:
    """A paying plan at its limit is warned once, then deduped within the cooldown."""
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Quota Store", "Main", plan="starter", email_prefix="quota")
            email, company_id = ctx["email"], ctx["company_id"]

        target_id = ctx["company_id"]

        async def _stub_entitlement(_db, company_id):
            if str(company_id) == target_id:
                # Paid plan, but capacity has been reached.
                return _StubEntitlement(_StubPlan(code="starter", name="Starter", max_stores=1, max_members=1))
            # Keep unrelated workspaces far below their limits so this pass only
            # exercises the caller under test.
            return _StubEntitlement(_StubPlan(code="pro", name="Pro", max_stores=1_000_000, max_members=1_000_000))

        monkeypatch.setattr(quota_warnings, "load_entitlement", _stub_entitlement)

        async with SessionLocal() as db:
            stats = await run_quota_warnings(db)
        assert stats["warned"] >= 1
        rows = await _warnings(email)
        assert len(rows) == 1
        assert "Starter" in rows[0].subject
        assert "plan limits" in rows[0].subject
        assert "<!DOCTYPE html>" in rows[0].body_html

        # A second pass within the cooldown must not re-send the same level.
        async with SessionLocal() as db:
            again = await run_quota_warnings(db)
        assert again["warned"] == 0
        assert len(await _warnings(email)) == 1
    finally:
        await _cleanup(email, company_id)
