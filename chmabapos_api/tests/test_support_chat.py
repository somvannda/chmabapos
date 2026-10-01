from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.services import ai as ai_service
from app.services import support


@pytest.mark.asyncio
async def test_answer_grounds_in_scoped_guides(monkeypatch) -> None:
    captured: dict = {}

    async def fake_complete_chat(db, *, system, messages, temperature=0.3, max_tokens=900):
        captured["system"] = system
        captured["messages"] = messages
        return {"content": "Open Point of sale, then tap the product.", "provider": "deepseek", "model": "deepseek-chat"}

    monkeypatch.setattr(ai_service, "complete_chat", fake_complete_chat)

    async with SessionLocal() as db:
        result = await support.answer(
            db,
            question="How do I ring up a sale?",
            history=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
            vertical="coffee",
            role="cashier",
        )

    assert result["provider"] == "deepseek"
    assert "getting-started.first-sale" in result["guide_ids"]
    # The system prompt carries the caller's vertical, role and the guide steps.
    assert "Business type: coffee" in captured["system"]
    assert "User role: cashier" in captured["system"]
    assert "Open Point of sale" in captured["system"]
    assert captured["messages"][-1] == {"role": "user", "content": "How do I ring up a sale?"}


@pytest.mark.asyncio
async def test_answer_requires_a_question() -> None:
    async with SessionLocal() as db:
        with pytest.raises(ValueError):
            await support.answer(db, question="   ", history=[], vertical="general", role="owner")


async def _setup_workspace(client, email: str, vertical: str) -> str:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Chat Owner", "password": "strong-password"})
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Chat Store", "store_name": "Main", "currency_code": "USD", "plan_code": "free", "vertical": vertical},
    )
    return setup.json()["company"]["id"], headers


async def _cleanup_company(company_id: str) -> None:
    async with SessionLocal() as db:
        parameters = {"company_id": company_id}
        statements = [
            "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id=memberships.id AND memberships.company_id=:company_id",
            "DELETE FROM memberships WHERE company_id=:company_id",
            "DELETE FROM company_currencies WHERE company_id=:company_id",
            "DELETE FROM categories WHERE company_id=:company_id",
            "DELETE FROM stores WHERE company_id=:company_id",
            "DELETE FROM subscriptions WHERE company_id=:company_id",
            "DELETE FROM companies WHERE id=:company_id",
        ]
        for statement in statements:
            await db.execute(text(statement), parameters)
        await db.commit()


async def _cleanup_user(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email=:email)"), {"email": email})
        await db.execute(text("DELETE FROM users WHERE email=:email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_support_chat_endpoint_returns_answer(monkeypatch) -> None:
    async def fake_complete_chat(db, *, system, messages, temperature=0.3, max_tokens=900):
        return {"content": "Tap Charge to complete the sale.", "provider": "openai", "model": "gpt-4o-mini"}

    monkeypatch.setattr(ai_service, "complete_chat", fake_complete_chat)

    email = f"chat-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            company_id, headers = await _setup_workspace(client, email, "coffee")
            chat = await client.post("/api/v1/support/chat", headers=headers, json={"message": "How do I ring up a sale?", "history": []})
            assert chat.status_code == 200
            body = chat.json()
            assert body["answer"] == "Tap Charge to complete the sale."
            assert body["provider"] == "openai"
            assert body["guide_ids"]
    finally:
        if company_id:
            await _cleanup_company(company_id)
        await _cleanup_user(email)


@pytest.mark.asyncio
async def test_support_chat_reports_unconfigured_ai(monkeypatch) -> None:
    async def fake_complete_chat(db, *, system, messages, temperature=0.3, max_tokens=900):
        raise ai_service.AINotConfiguredError("No AI provider is configured yet.")

    monkeypatch.setattr(ai_service, "complete_chat", fake_complete_chat)

    email = f"chat-nc-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            company_id, headers = await _setup_workspace(client, email, "general")
            chat = await client.post("/api/v1/support/chat", headers=headers, json={"message": "How do I add products?", "history": []})
            assert chat.status_code == 400
            assert "configured" in chat.json()["detail"].lower()
    finally:
        if company_id:
            await _cleanup_company(company_id)
        await _cleanup_user(email)


@pytest.mark.asyncio
async def test_answer_clamps_history(monkeypatch) -> None:
    captured: dict = {}

    async def fake_complete_chat(db, *, system, messages, temperature=0.3, max_tokens=900):
        captured["messages"] = messages
        return {"content": "ok", "provider": "x", "model": "y"}

    monkeypatch.setattr(ai_service, "complete_chat", fake_complete_chat)

    history = [{"role": "assistant" if i % 2 else "user", "content": f"turn {i}"} for i in range(20)]
    async with SessionLocal() as db:
        await support.answer(db, question="How do I add products?", history=history, vertical="general", role="owner")

    # Only the last N history turns plus the new question are sent to the provider.
    assert len(captured["messages"]) == settings.support_max_history_turns + 1
    assert captured["messages"][-1] == {"role": "user", "content": "How do I add products?"}


def test_check_rate_limit_window() -> None:
    key = f"rl-{uuid.uuid4().hex}"
    assert support.check_rate_limit(key, limit=2, window_seconds=60) is True
    assert support.check_rate_limit(key, limit=2, window_seconds=60) is True
    assert support.check_rate_limit(key, limit=2, window_seconds=60) is False
    # A non-positive limit disables limiting.
    assert support.check_rate_limit(f"{key}-off", limit=0) is True


@pytest.mark.asyncio
async def test_support_chat_rate_limited(monkeypatch) -> None:
    monkeypatch.setattr(settings, "support_rate_limit_per_hour", 1)

    async def fake_complete_chat(db, *, system, messages, temperature=0.3, max_tokens=900):
        return {"content": "ok", "provider": "x", "model": "y"}

    monkeypatch.setattr(ai_service, "complete_chat", fake_complete_chat)

    email = f"chat-rl-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            company_id, headers = await _setup_workspace(client, email, "general")
            first = await client.post("/api/v1/support/chat", headers=headers, json={"message": "How do I add products?", "history": []})
            assert first.status_code == 200
            second = await client.post("/api/v1/support/chat", headers=headers, json={"message": "How do I add products?", "history": []})
            assert second.status_code == 429
    finally:
        if company_id:
            await _cleanup_company(company_id)
        await _cleanup_user(email)


@pytest.mark.asyncio
async def test_support_escalate_records_and_flags_priority() -> None:
    email = f"esc-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            company_id, headers = await _setup_workspace(client, email, "general")
            res = await client.post(
                "/api/v1/support/escalate",
                headers=headers,
                json={
                    "message": "How do I combine two sales into one receipt?",
                    "history": [
                        {"role": "user", "content": "distinctive escalation transcript marker"},
                        {"role": "assistant", "content": "some earlier answer"},
                    ],
                    "guide_ids": ["getting-started.first-sale"],
                },
            )
            assert res.status_code == 200
            body = res.json()
            assert body["received"] is True
            # The free plan does not include the priority_support capability.
            assert body["priority"] is False
            assert body["detail"]
            assert "SUP-" in body["detail"]

        # The escalation carries context for the support team.
        async with SessionLocal() as db:
            row = (
                await db.execute(
                    text(
                        "SELECT details::text FROM platform_activities "
                        "WHERE event_type = 'support.escalated' AND company_id::text = :cid "
                        "ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"cid": company_id},
                )
            ).first()
        assert row is not None
        assert "distinctive escalation transcript marker" in row[0]
        assert "getting-started.first-sale" in row[0]
    finally:
        if company_id:
            await _cleanup_company(company_id)
        await _cleanup_user(email)


@pytest.mark.asyncio
async def test_support_chat_stream_endpoint(monkeypatch) -> None:
    async def fake_require(db):
        return None

    async def fake_stream(db, *, system, messages, temperature=0.3, max_tokens=900):
        for chunk in ("Tap ", "Charge."):
            yield chunk

    monkeypatch.setattr(ai_service, "require_chat_config", fake_require)
    monkeypatch.setattr(ai_service, "stream_chat", fake_stream)

    email = f"chat-stream-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            company_id, headers = await _setup_workspace(client, email, "general")
            async with client.stream(
                "POST",
                "/api/v1/support/chat/stream",
                headers=headers,
                json={"message": "How do I ring up a sale?", "history": []},
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                body = "".join([chunk async for chunk in response.aiter_text()])
            assert "Tap " in body
            assert "Charge." in body
            assert "[DONE]" in body
            # The stream cites its sources first.
            assert '"guides"' in body
    finally:
        if company_id:
            await _cleanup_company(company_id)
        await _cleanup_user(email)


@pytest.mark.asyncio
async def test_support_feedback_records(monkeypatch) -> None:
    email = f"chat-fb-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            company_id, headers = await _setup_workspace(client, email, "general")
            res = await client.post(
                "/api/v1/support/feedback",
                headers=headers,
                json={"rating": "down", "question": "How do I refund an order?", "answer": "Sorry, not sure.", "guide_ids": ["getting-started.first-sale"]},
            )
            assert res.status_code == 200
            assert res.json()["received"] is True

            # A bad rating value is rejected.
            bad = await client.post(
                "/api/v1/support/feedback",
                headers=headers,
                json={"rating": "maybe", "question": "x"},
            )
            assert bad.status_code == 422
    finally:
        if company_id:
            await _cleanup_company(company_id)
        await _cleanup_user(email)


@pytest.mark.asyncio
async def test_support_conversation_persistence(monkeypatch) -> None:
    async def fake_complete_chat(db, *, system, messages, temperature=0.3, max_tokens=900):
        return {"content": "Tap Charge.", "provider": "x", "model": "y"}

    monkeypatch.setattr(ai_service, "complete_chat", fake_complete_chat)

    email = f"chat-conv-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            company_id, headers = await _setup_workspace(client, email, "general")

            first = await client.post("/api/v1/support/chat", headers=headers, json={"message": "How do I ring up a sale?", "history": []})
            assert first.status_code == 200
            conversation_id = first.json()["conversation_id"]
            assert conversation_id

            # A follow-up appends to the same conversation.
            second = await client.post(
                "/api/v1/support/chat",
                headers=headers,
                json={"message": "And a refund?", "history": [], "conversation_id": conversation_id},
            )
            assert second.status_code == 200
            assert second.json()["conversation_id"] == conversation_id

            listing = await client.get("/api/v1/support/conversations", headers=headers)
            assert listing.status_code == 200
            assert conversation_id in [row["id"] for row in listing.json()]

            detail = await client.get(f"/api/v1/support/conversations/{conversation_id}", headers=headers)
            assert detail.status_code == 200
            assert [message["role"] for message in detail.json()["messages"]] == ["user", "assistant", "user", "assistant"]

            # An unknown conversation id is a 404, not a new thread.
            missing = await client.post(
                "/api/v1/support/chat",
                headers=headers,
                json={"message": "hi", "history": [], "conversation_id": "00000000-0000-0000-0000-000000000000"},
            )
            assert missing.status_code == 404

            deleted = await client.delete(f"/api/v1/support/conversations/{conversation_id}", headers=headers)
            assert deleted.status_code == 204
            gone = await client.get(f"/api/v1/support/conversations/{conversation_id}", headers=headers)
            assert gone.status_code == 404
    finally:
        if company_id:
            await _cleanup_company(company_id)
        await _cleanup_user(email)
