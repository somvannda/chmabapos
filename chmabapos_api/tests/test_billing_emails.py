"""Billing emails: the payment receipt and the payment-failure notice."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend
from app.services.billing_emails import queue_billing_failure_email
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _receipts(owner_email: str | None) -> list[EmailSend]:
    if not owner_email:
        return []
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(EmailSend)
                .where(EmailSend.recipient_email == owner_email, EmailSend.source == "billing_receipt")
                .order_by(EmailSend.created_at)
            )
        ).scalars().all()
        for row in rows:
            db.expunge(row)
        return rows


@pytest.mark.asyncio
async def test_paid_checkout_queues_a_receipt_email() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Completing the Starter checkout exercises fulfill_billing_payment,
            # which issues the receipt this email is built from.
            ctx = await register_and_setup(client, "Billing Mail Store", "Main", plan="starter", email_prefix="billing-mail")
            email, company_id = ctx["email"], ctx["company_id"]

            receipts = await _receipts(email)
            assert len(receipts) == 1
            subject, body = receipts[0].subject, receipts[0].body_html
            assert subject.startswith("Payment received")
            assert "<!DOCTYPE html>" in body
            assert "Starter" in body
            assert "Valid until" in body
    finally:
        if email:
            async with SessionLocal() as db:
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
                await db.commit()
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_billing_failure_email_queues_to_owners() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Failure Mail Store", "Main", plan="free", email_prefix="billing-fail")
            email, company_id = ctx["email"], ctx["company_id"]
            async with SessionLocal() as db:
                queued = await queue_billing_failure_email(
                    db,
                    company_id=uuid.UUID(company_id),
                    plan_code="starter",
                    amount=Decimal("19.00"),
                    currency_code="USD",
                    reason="failed",
                )
                await db.commit()
            assert queued == 1
            async with SessionLocal() as db:
                rows = (
                    await db.execute(
                        select(EmailSend).where(EmailSend.recipient_email == email, EmailSend.source == "billing_failure")
                    )
                ).scalars().all()
            assert len(rows) == 1
            assert rows[0].subject.startswith("Payment did not go through")
            assert "<!DOCTYPE html>" in rows[0].body_html
            assert "Starter" in rows[0].body_html
    finally:
        if email:
            async with SessionLocal() as db:
                await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
                await db.commit()
        if company_id:
            await cleanup_company(company_id, [email] if email else [])
