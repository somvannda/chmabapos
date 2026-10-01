from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app


async def _cleanup(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        if company_id:
            parameters = {"company_id": company_id}
            for statement in (
                "DELETE FROM support_tickets WHERE company_id=:company_id",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id=memberships.id AND memberships.company_id=:company_id",
                "DELETE FROM memberships WHERE company_id=:company_id",
                "DELETE FROM company_currencies WHERE company_id=:company_id",
                "DELETE FROM categories WHERE company_id=:company_id",
                "DELETE FROM stores WHERE company_id=:company_id",
                "DELETE FROM subscriptions WHERE company_id=:company_id",
                "DELETE FROM companies WHERE id=:company_id",
            ):
                await db.execute(text(statement), parameters)
        await db.execute(text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email=:email)"), {"email": email})
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email=:email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email=:email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_support_ticket_lifecycle() -> None:
    email = f"tickets-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Ticket Owner", "password": "strong-password"})
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await client.post(
                "/api/v1/workspaces/setup",
                headers=headers,
                json={"company_name": "Ticket Store", "store_name": "Main", "currency_code": "USD", "plan_code": "free", "vertical": "general"},
            )
            company_id = setup.json()["company"]["id"]

            escalation = await client.post(
                "/api/v1/support/escalate",
                headers=headers,
                json={
                    "message": "How do I combine two sales into one receipt?",
                    "history": [
                        {"role": "user", "content": "how do I refund an order?"},
                        {"role": "assistant", "content": "Open the order and choose Refund."},
                    ],
                },
            )
            assert escalation.status_code == 200
            reference = next(part.rstrip(".") for part in escalation.json()["detail"].split() if part.startswith("SUP-"))

            # The merchant can see their request and its status.
            mine = await client.get("/api/v1/support/tickets", headers=headers)
            assert mine.status_code == 200
            ticket = next(row for row in mine.json() if row["reference"] == reference)
            assert ticket["status"] == "open"
            assert "combine two sales" in ticket["question"]

            # A platform admin can work the ticket.
            async with SessionLocal() as db:
                await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": email})
                await db.commit()
            listing = await client.get("/api/v1/admin/support/tickets", headers=headers)
            assert listing.status_code == 200
            admin_ticket = next(row for row in listing.json() if row["reference"] == reference)
            ticket_id = admin_ticket["id"]

            # Agent reply threads onto the ticket and flips it to pending.
            reply = await client.post(f"/api/v1/admin/support/tickets/{ticket_id}/reply", headers=headers, json={"body": "Use the combine action at checkout."})
            assert reply.status_code == 201
            assert reply.json()["status"] == "pending"
            assert any(message["author_type"] == "agent" for message in reply.json()["messages"])
            # The assistant context is attached as a system message for the team.
            assert any(message["author_type"] == "system" for message in reply.json()["messages"])

            # The merchant sees the agent reply (system context hidden) and replies back.
            merchant_detail = await client.get(f"/api/v1/support/tickets/{ticket_id}", headers=headers)
            assert merchant_detail.status_code == 200
            assert all(message["author_type"] != "system" for message in merchant_detail.json()["messages"])
            assert any(message["author_type"] == "agent" for message in merchant_detail.json()["messages"])

            merchant_reply = await client.post(f"/api/v1/support/tickets/{ticket_id}/reply", headers=headers, json={"body": "It worked, thanks!"})
            assert merchant_reply.status_code == 201
            assert merchant_reply.json()["status"] == "open"  # a merchant reply reopens it

            # Status transitions keep the ticket (never deleted).
            resolved = await client.patch(f"/api/v1/admin/support/tickets/{ticket_id}", headers=headers, json={"status": "resolved", "resolution_note": "Glad it worked."})
            assert resolved.status_code == 200
            assert resolved.json()["status"] == "resolved"
            assert resolved.json()["resolved_at"] is not None

            reopened = await client.patch(f"/api/v1/admin/support/tickets/{ticket_id}", headers=headers, json={"status": "open"})
            assert reopened.status_code == 200 and reopened.json()["status"] == "open"
            closed = await client.patch(f"/api/v1/admin/support/tickets/{ticket_id}", headers=headers, json={"status": "closed"})
            assert closed.status_code == 200 and closed.json()["status"] == "closed"

            # The ticket is still visible after closing.
            mine_after = await client.get("/api/v1/support/tickets", headers=headers)
            updated = next(row for row in mine_after.json() if row["reference"] == reference)
            assert updated["status"] == "closed"
    finally:
        await _cleanup(email, company_id)
