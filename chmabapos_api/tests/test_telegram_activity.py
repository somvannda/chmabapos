from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import PlatformActivity
from app.services.activity import render_activity
from app.services.telegram_digest import run_daily_digest
from app.telegram import send_telegram_message

PASSWORD = "strong-password"


async def cleanup(email: str) -> None:
    async with SessionLocal() as db:
        parameters = {"email": email}
        await db.execute(text("DELETE FROM platform_activities WHERE email = :email"), parameters)
        await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), parameters)
        await db.execute(text("DELETE FROM password_reset_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), parameters)
        await db.execute(text("DELETE FROM users WHERE email = :email"), parameters)
        await db.commit()


def new_email(prefix: str) -> str:
    return f"tg-{prefix}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.asyncio
async def test_auth_events_are_recorded() -> None:
    email = new_email("auth")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Telegram User", "password": PASSWORD})
            assert register.status_code == 201
            assert (await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})).status_code == 200
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
            assert login.status_code == 200
        async with SessionLocal() as db:
            rows = (
                await db.execute(select(PlatformActivity).where(PlatformActivity.email == email).order_by(PlatformActivity.created_at))
            ).scalars().all()
            event_types = [row.event_type for row in rows]
            assert "user.registered" in event_types
            assert "user.email_verified" in event_types
            assert "user.logged_in" in event_types
            assert all(row.user_id is not None for row in rows)
    finally:
        await cleanup(email)


@pytest.mark.asyncio
async def test_invalid_login_does_not_record_server_error() -> None:
    email = new_email("badlogin")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Bad Login", "password": PASSWORD})
            assert register.status_code == 201
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            assert (await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})).status_code == 401
        async with SessionLocal() as db:
            count = len((await db.execute(select(PlatformActivity).where(PlatformActivity.email == email, PlatformActivity.event_type == "user.logged_in"))).scalars().all())
            assert count == 0
    finally:
        await cleanup(email)


@pytest.mark.asyncio
async def test_daily_digest_posts_recap(monkeypatch) -> None:
    email = new_email("digest")
    captured: dict[str, str] = {}

    async def fake_send(body: str, **_: object) -> bool:
        captured["body"] = body
        return True

    monkeypatch.setattr("app.services.telegram_digest.send_telegram_message", fake_send)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Digest User", "password": PASSWORD})
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        async with SessionLocal() as db:
            stats = await run_daily_digest(db)
        assert stats["sent"] is True
        assert stats["signups"] >= 1
        assert stats["logins"] >= 1
        body = captured["body"]
        assert "Chmaba daily recap" in body
        assert "New signups:" in body
        assert "Logins:" in body
        assert "Paid orders:" in body
    finally:
        await cleanup(email)


@pytest.mark.asyncio
async def test_telegram_disabled_is_noop(monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_bot_token", None)
    monkeypatch.setattr(settings, "telegram_chat_id", None)
    assert settings.telegram_enabled is False
    assert await send_telegram_message("should not send") is False


@pytest.mark.asyncio
async def test_a_local_instance_never_calls_the_telegram_api(monkeypatch) -> None:
    """The 12 Nov page: real chat credentials in a dev .env must stay local."""
    monkeypatch.setattr(settings, "telegram_bot_token", "123456:local-test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "-1001234567890")
    monkeypatch.setattr(settings, "environment", "development")

    def explode(*args, **kwargs):  # noqa: ANN002, ANN003 - must not be reached
        raise AssertionError("a development instance must not reach api.telegram.org")

    monkeypatch.setattr("app.telegram.httpx.AsyncClient", explode)

    assert settings.telegram_enabled is True  # configured, and still silent
    assert await send_telegram_message("local activity") is False


@pytest.mark.asyncio
async def test_production_still_posts_to_the_chat(monkeypatch) -> None:
    posted: dict = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> bool:
            return False

        async def post(self, url: str, json: dict):
            posted["url"] = url
            posted["json"] = json
            return FakeResponse()

    monkeypatch.setattr(settings, "telegram_bot_token", "123456:prod-test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "-1001234567890")
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr("app.telegram.httpx.AsyncClient", FakeClient)

    assert await send_telegram_message("real alert") is True
    assert posted["json"]["chat_id"] == "-1001234567890"
    assert posted["json"]["text"] == "real alert"


def test_render_activity_includes_title_and_details() -> None:
    body = render_activity("order.paid", details={"store": "Main Counter", "order_number": "CHM-000001", "amount": "12.50 USD"})
    assert body.startswith("Sale completed")
    assert "Store: Main Counter" in body
    assert "Order: CHM-000001" in body
    assert "Amount: 12.50 USD" in body
