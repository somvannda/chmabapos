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


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"chmaba-test" * 8


async def _upload(client, headers, path, filename="ref.png"):
    return await client.post(path, headers=headers, files={"file": (filename, PNG_BYTES, "image/png")})


@pytest.mark.asyncio
async def test_support_ticket_attachments_and_notifications() -> None:
    email = f"tickets-attach-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Attach Owner", "password": "strong-password"})
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await client.post(
                "/api/v1/workspaces/setup",
                headers=headers,
                json={"company_name": "Attach Store", "store_name": "Main", "currency_code": "USD", "plan_code": "free", "vertical": "general"},
            )
            company_id = setup.json()["company"]["id"]

            # Only image suffixes are accepted.
            bad = await _upload(client, headers, "/api/v1/support/attachments", filename="notes.txt")
            assert bad.status_code == 400

            # Merchant stages two reference images and opens the ticket with them.
            first = await _upload(client, headers, "/api/v1/support/attachments")
            second = await _upload(client, headers, "/api/v1/support/attachments")
            assert first.status_code == 201 and second.status_code == 201
            attachment_ids = [first.json()["id"], second.json()["id"]]

            escalation = await client.post(
                "/api/v1/support/escalate",
                headers=headers,
                json={"message": "The date is wrong on the dashboard.", "attachment_ids": attachment_ids},
            )
            assert escalation.status_code == 200
            reference = next(part.rstrip(".") for part in escalation.json()["detail"].split() if part.startswith("SUP-"))
            mine = await client.get("/api/v1/support/tickets", headers=headers)
            ticket_id = next(row["id"] for row in mine.json() if row["reference"] == reference)

            opened = await client.get(f"/api/v1/support/tickets/{ticket_id}", headers=headers)
            assert opened.status_code == 200
            assert len(opened.json()["attachments"]) == 2
            assert all(row["url"].startswith("/media/") for row in opened.json()["attachments"])
            assert all(message["attachments"] == [] for message in opened.json()["messages"])

            # A staged image can only be claimed once.
            again = await client.post(
                f"/api/v1/support/tickets/{ticket_id}/reply",
                headers=headers,
                json={"body": "Retry", "attachment_ids": [attachment_ids[0]]},
            )
            assert again.status_code == 400

            async with SessionLocal() as db:
                await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": email})
                await db.commit()

            # Agent replies with an image; the merchant gets an in-app notification.
            agent_file = await client.post(
                "/api/v1/admin/support/attachments",
                headers=headers,
                data={"ticket_id": ticket_id},
                files={"file": ("agent.png", PNG_BYTES, "image/png")},
            )
            assert agent_file.status_code == 201
            reply = await client.post(
                f"/api/v1/admin/support/tickets/{ticket_id}/reply",
                headers=headers,
                json={"body": "Can you attach a screenshot of the dashboard?", "attachment_ids": [agent_file.json()["id"]]},
            )
            assert reply.status_code == 201
            agent_message = next(message for message in reply.json()["messages"] if message["author_type"] == "agent")
            assert len(agent_message["attachments"]) == 1

            notifications = await client.get("/api/v1/notifications", headers=headers)
            assert notifications.status_code == 200
            assert any(row["type"] == "support_reply" for row in notifications.json())

            # Merchant replies with another image; it lands on their message.
            merchant_file = await _upload(client, headers, "/api/v1/support/attachments", filename="merchant.png")
            assert merchant_file.status_code == 201
            merchant_reply = await client.post(
                f"/api/v1/support/tickets/{ticket_id}/reply",
                headers=headers,
                json={"body": "Here it is.", "attachment_ids": [merchant_file.json()["id"]]},
            )
            assert merchant_reply.status_code == 201
            merchant_message = next(message for message in merchant_reply.json()["messages"] if message["author_type"] == "merchant")
            assert len(merchant_message["attachments"]) == 1

            # A status change also rings the bell.
            resolved = await client.patch(
                f"/api/v1/admin/support/tickets/{ticket_id}",
                headers=headers,
                json={"status": "resolved", "resolution_note": "Fixed the timezone."},
            )
            assert resolved.status_code == 200
            notifications_after = await client.get("/api/v1/notifications", headers=headers)
            assert any(row["type"] == "support_update" for row in notifications_after.json())
    finally:
        await _cleanup(email, company_id)


@pytest.mark.asyncio
async def test_support_ticket_ai_replies_and_html_sanitising(monkeypatch) -> None:
    email = f"tickets-ai-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "AI Owner", "password": "strong-password"})
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await client.post(
                "/api/v1/workspaces/setup",
                headers=headers,
                json={"company_name": "AI Store", "store_name": "Main", "currency_code": "USD", "plan_code": "free", "vertical": "general"},
            )
            company_id = setup.json()["company"]["id"]

            escalation = await client.post(
                "/api/v1/support/escalate",
                headers=headers,
                json={"message": "How do I edit a product's price?"},
            )
            reference = next(part.rstrip(".") for part in escalation.json()["detail"].split() if part.startswith("SUP-"))
            mine = await client.get("/api/v1/support/tickets", headers=headers)
            ticket_id = next(row["id"] for row in mine.json() if row["reference"] == reference)

            async with SessionLocal() as db:
                await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": email})
                await db.commit()

            async def fake_complete_chat(db, *, system, messages, temperature=0.3, max_tokens=900):
                return {"content": "Here is a clearer reply.", "provider": "test", "model": "test-model", "usage": {"prompt_tokens": 1, "completion_tokens": 2}}

            monkeypatch.setattr("app.services.ai.complete_chat", fake_complete_chat)
            draft = await client.post(
                f"/api/v1/admin/support/tickets/{ticket_id}/ai-draft",
                headers=headers,
                json={"body": "rough note"},
            )
            assert draft.status_code == 200
            assert draft.json()["body"] == "Here is a clearer reply."

            async def fake_answer(db, **kwargs):
                return {"answer": "Open Inventory, then edit the product.", "provider": "test", "model": "test-model", "guide_ids": ["inventory.edit"]}

            monkeypatch.setattr("app.services.support.answer", fake_answer)
            suggest = await client.post(f"/api/v1/admin/support/tickets/{ticket_id}/ai-suggest", headers=headers)
            assert suggest.status_code == 200
            assert "Inventory" in suggest.json()["body"]

            # A reply's HTML is sanitised before it is stored and shown back.
            reply = await client.post(
                f"/api/v1/admin/support/tickets/{ticket_id}/reply",
                headers=headers,
                json={"body": '<p>Hello <strong>there</strong></p><script>alert(1)</script>'},
            )
            assert reply.status_code == 201
            agent_message = next(message for message in reply.json()["messages"] if message["author_type"] == "agent")
            assert "<strong>there</strong>" in agent_message["body"]
            assert "<script" not in agent_message["body"].lower()
    finally:
        await _cleanup(email, company_id)
