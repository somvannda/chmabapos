"""Owner warnings when a workspace nears its plan limits."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
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


@pytest.mark.asyncio
async def test_quota_warning_emails_owner_and_dedupes() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # On the Free plan a workspace is already at its limits (1 store, 1 seat).
            ctx = await register_and_setup(client, "Quota Store", "Main", plan="free", email_prefix="quota")
            email, company_id = ctx["email"], ctx["company_id"]

        async with SessionLocal() as db:
            stats = await run_quota_warnings(db)
        assert stats["warned"] >= 1
        rows = await _warnings(email)
        assert len(rows) == 1
        assert "plan limits" in rows[0].subject
        assert "<!DOCTYPE html>" in rows[0].body_html

        # A second pass within the cooldown must not re-send the same level.
        async with SessionLocal() as db:
            again = await run_quota_warnings(db)
        assert again["warned"] == 0
        assert len(await _warnings(email)) == 1
    finally:
        if email:
            async with SessionLocal() as db:
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
                await db.commit()
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
