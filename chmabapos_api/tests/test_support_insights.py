from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.models import PlatformActivity


@pytest.mark.asyncio
async def test_support_insights_rollup() -> None:
    email = f"insights-{uuid.uuid4().hex[:10]}@example.com"
    questions = ("How do I refund an order?", "How do I ring up a sale?", "Need help", "How do I refund a subscription?")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Insights Admin", "password": "strong-password"})
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            async with SessionLocal() as db:
                await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": email})
                # Isolate the aggregate from any support rows other tests left behind.
                await db.execute(text("DELETE FROM platform_activities WHERE event_type IN ('support.feedback', 'support.escalated', 'support.no_match')"))
                db.add_all(
                    [
                        PlatformActivity(event_type="support.feedback", details={"rating": "down", "question": questions[0], "guide_ids": []}),
                        PlatformActivity(event_type="support.feedback", details={"rating": "down", "question": questions[0], "guide_ids": []}),
                        PlatformActivity(event_type="support.feedback", details={"rating": "up", "question": questions[1], "guide_ids": []}),
                        PlatformActivity(event_type="support.escalated", details={"question": questions[2]}),
                        PlatformActivity(event_type="support.no_match", details={"question": questions[3], "vertical": "general"}),
                    ]
                )
                await db.commit()

            res = await client.get("/api/v1/admin/support/insights", headers=headers)
            assert res.status_code == 200
            body = res.json()
            assert body["feedback_up"] == 1
            assert body["feedback_down"] == 2
            assert body["escalations"] == 1
            assert body["satisfaction_rate"] is not None
            # The most down-voted question ranks first.
            assert body["top_questions"][0]["question"] == questions[0]
            assert body["top_questions"][0]["down"] == 2
            assert body["top_questions"][0]["total"] == 2
            # Questions no guide matched are surfaced as content gaps.
            assert body["uncovered_questions"][0]["question"] == questions[3]
            assert body["uncovered_questions"][0]["total"] == 1
    finally:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM platform_activities WHERE event_type IN ('support.feedback', 'support.escalated', 'support.no_match')"))
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email=:email)"), {"email": email})
            await db.execute(text("DELETE FROM users WHERE email=:email"), {"email": email})
            await db.commit()
