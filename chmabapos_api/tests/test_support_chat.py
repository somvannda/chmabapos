"""Live support chat: hand-off, agent reply, tenancy and Telegram cadence.

These tests drive the real ASGI app against the test database. They deliberately
avoid ``/ask`` (which needs an AI provider) and exercise the human path, because
that is the part a merchant relies on when the assistant cannot help.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.services import activity as activity_service


async def create_workspace(client: AsyncClient, label: str = "Support") -> tuple[str, dict, dict]:
    email = f"{label.lower()}-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": f"{label} Owner", "password": "strong-password"},
    )
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={
            "company_name": f"{label} Co",
            "store_name": f"{label} Counter",
            "country": "Cambodia",
            "currency_code": "USD",
            "plan_code": "starter",
        },
    )
    assert setup.status_code == 201, setup.text
    await client.post(
        f"/api/v1/mock/chamabapay/{setup.json()['billing_payment']['external_id']}/complete",
        headers=headers,
    )
    return email, headers, setup.json()


async def promote_to_admin(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(
            text("UPDATE users SET platform_role = 'admin' WHERE email = :email"),
            {"email": email},
        )
        await db.commit()


async def cleanup(email: str, company_id: str | None) -> None:
    async with SessionLocal() as db:
        await db.execute(
            text(
                "DELETE FROM platform_activities WHERE company_id = :company_id "
                "OR user_id IN (SELECT id FROM users WHERE email = :email)"
            ),
            {"company_id": company_id, "email": email},
        )
        await db.execute(
            text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email = :email)"),
            {"email": email},
        )
        if company_id:
            parameters = {"company_id": company_id}
            statements = [
                "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                "DELETE FROM billing_receipts WHERE company_id = :company_id",
                "DELETE FROM billing_refunds WHERE company_id = :company_id",
                "DELETE FROM subscription_capacity_actions WHERE company_id = :company_id",
                "DELETE FROM subscriptions WHERE company_id = :company_id",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM invitations WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM categories WHERE company_id = :company_id",
                "DELETE FROM support_chat_messages USING support_chat_conversations WHERE support_chat_messages.conversation_id = support_chat_conversations.id AND support_chat_conversations.company_id = :company_id",
                "DELETE FROM support_chat_conversations WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]
            for statement in statements:
                await db.execute(text(statement), parameters)
        await db.execute(
            text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"),
            {"email": email},
        )
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_handoff_and_agent_reply_share_one_thread() -> None:
    email = ""
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            email, headers, setup = await create_workspace(client, "Handoff")
            company_id = setup["company"]["id"]
            started = await client.post(
                "/api/v1/support/chat/conversations",
                headers=headers,
                json={"subject": "Card reader", "body": "My card reader stopped connecting."},
            )
            assert started.status_code == 201, started.text
            conversation = started.json()
            assert conversation["status"] == "ai"
            conversation_id = conversation["id"]
            assert conversation["reference"].startswith("SUP-")
            assert any(message["author_type"] == "merchant" for message in conversation["messages"])

            handoff = await client.post(
                f"/api/v1/support/chat/conversations/{conversation_id}/handoff",
                headers=headers,
                json={"topic": "Card reader", "note": "Tried two cables."},
            )
            assert handoff.status_code == 200, handoff.text
            assert handoff.json()["status"] == "waiting"
            assert handoff.json()["handoff_requested_at"]

            # The merchant can keep typing while waiting.
            sent = await client.post(
                f"/api/v1/support/chat/conversations/{conversation_id}/messages",
                headers=headers,
                json={"body": "It shows a red light now."},
            )
            assert sent.status_code == 201, sent.text
            assert sent.json()["conversation"]["status"] == "waiting"

            await promote_to_admin(email)

            ops_list = await client.get(
                "/api/v1/admin/support/chat/conversations",
                headers=headers,
                params={"status": "waiting"},
            )
            assert ops_list.status_code == 200, ops_list.text
            assert any(row["id"] == conversation_id for row in ops_list.json())

            detail = await client.get(
                f"/api/v1/admin/support/chat/conversations/{conversation_id}",
                headers=headers,
            )
            assert detail.status_code == 200, detail.text
            assert detail.json()["merchant_email"] == email
            assert detail.json()["internal_notes"] is None
            assert [m["author_type"] for m in detail.json()["messages"]][-1] == "merchant"

            reply = await client.post(
                f"/api/v1/admin/support/chat/conversations/{conversation_id}/messages",
                headers=headers,
                json={"body": "Unplug it for ten seconds, then reconnect the USB cable."},
            )
            assert reply.status_code == 201, reply.text
            body = reply.json()
            assert body["conversation"]["status"] == "live"
            assert body["message"]["author_type"] == "agent"
            assert body["conversation"]["assigned_admin_id"]

            # The merchant sees the same thread, including the agent's name.
            merchant_thread = await client.get(
                f"/api/v1/support/chat/conversations/{conversation_id}",
                headers=headers,
            )
            assert merchant_thread.status_code == 200, merchant_thread.text
            last = merchant_thread.json()["messages"][-1]
            assert last["author_type"] == "agent"
            assert last["author_name"] == "Handoff Owner"

            async with SessionLocal() as db:
                link = f"support?conversation={conversation_id}"
                count = await db.scalar(
                    text("SELECT count(*) FROM notifications WHERE link = :link"),
                    {"link": link},
                )
            assert count and count >= 1
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_support_chat_is_company_scoped_and_admin_gated() -> None:
    owner_email = ""
    other_email = ""
    setup = {"company": {"id": None}}
    other_setup = {"company": {"id": None}}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            owner_email, owner_headers, setup = await create_workspace(client, "Scoped")
            other_email, other_headers, other_setup = await create_workspace(client, "Other")
            started = await client.post(
                "/api/v1/support/chat/conversations",
                headers=owner_headers,
                json={"body": "How do I change my plan?"},
            )
            assert started.status_code == 201, started.text
            conversation_id = started.json()["id"]

            blocked = await client.get(
                f"/api/v1/support/chat/conversations/{conversation_id}",
                headers=other_headers,
            )
            assert blocked.status_code == 404

            other_list = await client.get("/api/v1/support/chat/conversations", headers=other_headers)
            assert other_list.status_code == 200
            assert other_list.json() == []

            # A merchant token cannot reach the operations inbox.
            forbidden = await client.get(
                "/api/v1/admin/support/chat/conversations",
                headers=owner_headers,
            )
            assert forbidden.status_code in (401, 403)
    finally:
        await cleanup(owner_email, setup["company"]["id"])
        await cleanup(other_email, other_setup["company"]["id"])


@pytest.mark.asyncio
async def test_telegram_alerts_once_per_unanswered_burst(monkeypatch) -> None:
    sent: list[str] = []

    async def fake_send(text_value: str, *, chat_id: str | None = None) -> bool:
        sent.append(text_value)
        return True

    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "test-chat")
    monkeypatch.setattr(settings, "platform_admin_url", "https://admin.example.com")
    monkeypatch.setattr(activity_service, "send_telegram_message", fake_send)

    email = ""
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            email, headers, setup = await create_workspace(client, "Alerts")
            company_id = setup["company"]["id"]
            started = await client.post(
                "/api/v1/support/chat/conversations",
                headers=headers,
                json={"body": "Billing question"},
            )
            conversation_id = started.json()["id"]
            reference = started.json()["reference"]

            handoff = await client.post(
                f"/api/v1/support/chat/conversations/{conversation_id}/handoff",
                headers=headers,
                json={"note": "Please call me."},
            )
            assert handoff.status_code == 200
            support_sent = [item for item in sent if "Live support requested" in item or "Merchant is waiting" in item]
            assert len(support_sent) == 1
            assert "Live support requested" in support_sent[0]
            assert reference in support_sent[0]
            assert f"https://admin.example.com/support?conversation={conversation_id}" in support_sent[0]

            await client.post(
                f"/api/v1/support/chat/conversations/{conversation_id}/messages",
                headers=headers,
                json={"body": "Still waiting."},
            )
            assert len([item for item in sent if "Live support requested" in item or "Merchant is waiting" in item]) == 1, "a follow-up in the same unanswered burst must not page again"

            await promote_to_admin(email)
            await client.post(
                f"/api/v1/admin/support/chat/conversations/{conversation_id}/messages",
                headers=headers,
                json={"body": "I am here."},
            )
            await client.post(
                f"/api/v1/support/chat/conversations/{conversation_id}/messages",
                headers=headers,
                json={"body": "Thanks, one more thing."},
            )
            assert len([item for item in sent if "Live support requested" in item or "Merchant is waiting" in item]) == 2, "a new merchant message after a reply starts a new burst"
    finally:
        await cleanup(email, company_id)


@pytest.mark.asyncio
async def test_cashier_only_sees_their_own_support_threads() -> None:
    owner_email = ""
    setup: dict = {}
    cashier_email = ""
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            owner_email, owner_headers, setup = await create_workspace(client, "Privacy")
            started = await client.post(
                "/api/v1/support/chat/conversations",
                headers=owner_headers,
                json={"body": "Billing question from the owner"},
            )
            assert started.status_code == 201
            conversation_id = started.json()["id"]

            cashier_email = f"privacy-cashier-{uuid.uuid4().hex[:10]}@example.com"
            invite = await client.post(
                "/api/v1/team/invitations",
                headers=owner_headers,
                json={"email": cashier_email, "role": "cashier", "store_ids": [setup["store"]["id"]]},
            )
            assert invite.status_code == 201, invite.text
            accepted = await client.post(
                "/api/v1/team/invitations/accept",
                json={
                    "token": invite.json()["dev_invitation_token"],
                    "full_name": "Privacy Cashier",
                    "password": "strong-password",
                },
            )
            assert accepted.status_code == 200, accepted.text
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": cashier_email, "password": "strong-password"},
            )
            cashier_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            hidden = await client.get(
                f"/api/v1/support/chat/conversations/{conversation_id}",
                headers=cashier_headers,
            )
            assert hidden.status_code == 404

            cashier_list = await client.get("/api/v1/support/chat/conversations", headers=cashier_headers)
            assert cashier_list.status_code == 200
            assert cashier_list.json() == []

            own = await client.post(
                "/api/v1/support/chat/conversations",
                headers=cashier_headers,
                json={"body": "Printer on till 2"},
            )
            assert own.status_code == 201
            owner_list = await client.get("/api/v1/support/chat/conversations", headers=owner_headers)
            owner_ids = {row["id"] for row in owner_list.json()}
            assert own.json()["id"] in owner_ids
            assert conversation_id in owner_ids
    finally:
        if owner_email:
            await cleanup(owner_email, setup.get("company", {}).get("id"))
        if cashier_email:
            await cleanup(cashier_email, None)


@pytest.mark.asyncio
async def test_closed_thread_reopens_on_a_new_message() -> None:
    email = ""
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            email, headers, setup = await create_workspace(client, "Reopen")
            company_id = setup["company"]["id"]
            started = await client.post(
                "/api/v1/support/chat/conversations",
                headers=headers,
                json={"body": "Printer not detected"},
            )
            conversation_id = started.json()["id"]
            closed = await client.post(
                f"/api/v1/support/chat/conversations/{conversation_id}/close",
                headers=headers,
            )
            assert closed.status_code == 200
            assert closed.json()["status"] == "closed"

            reopened = await client.post(
                f"/api/v1/support/chat/conversations/{conversation_id}/messages",
                headers=headers,
                json={"body": "It happened again."},
            )
            assert reopened.status_code == 201
            assert reopened.json()["conversation"]["status"] == "waiting"
    finally:
        await cleanup(email, company_id)
