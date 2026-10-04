"""Monthly sales summary email."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
from app.services.store_notifications import run_store_notifications
from tests.test_lifecycle import cleanup_company, register_and_setup

# 1 Feb 2026 14:00 UTC is 21:00 local (UTC+7): first of the month, past the hour.
FIRST_OF_MONTH_UTC = datetime(2026, 2, 1, 14, 0, tzinfo=timezone.utc)


async def _notes(owner_email: str | None) -> list[EmailSend]:
    if not owner_email:
        return []
    async with SessionLocal() as db:
        rows = (
            await db.execute(select(EmailSend).where(EmailSend.recipient_email == owner_email, EmailSend.source == "store_note"))
        ).scalars().all()
        for row in rows:
            db.expunge(row)
        return rows


@pytest.mark.asyncio
async def test_monthly_report_is_opt_in_and_sends_once_a_month() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Monthly Store", "Main", plan="free", email_prefix="monthly")
            email, company_id = ctx["email"], ctx["company_id"]
            headers = ctx["headers"]

            # Off by default: nothing is queued.
            async with SessionLocal() as db:
                await run_store_notifications(db, now=FIRST_OF_MONTH_UTC)
            assert await _notes(email) == []

            await client.patch(f"/api/v1/stores/{ctx['store_id']}", headers=headers, json={"preferences": {"notifications": {"monthly_report": True}}})
            async with SessionLocal() as db:
                stats = await run_store_notifications(db, now=FIRST_OF_MONTH_UTC)
            assert stats["monthly_reports"] == 1
            notes = await _notes(email)
            assert len(notes) == 1
            assert notes[0].subject.startswith("Monthly summary")
            assert "<!DOCTYPE html>" in notes[0].body_html

            # A second run the same month must not double-send.
            async with SessionLocal() as db:
                again = await run_store_notifications(db, now=FIRST_OF_MONTH_UTC)
            assert again["monthly_reports"] == 0
            assert len(await _notes(email)) == 1
    finally:
        if email:
            async with SessionLocal() as db:
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
                await db.commit()
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
