"""Outbound mail provider settings: SMTP/Resend selection, masking, test send."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app

MAIL_SETTING_KEYS = ("mail_provider", "mail_from", "mail_from_name", "mail_reply_to", "resend_api_key")


async def register_verified(client: AsyncClient, email: str, *, workspace: bool = False) -> None:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Mail Tester", "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    if workspace:
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        setup = await client.post(
            "/api/v1/workspaces/setup",
            headers=headers,
            json={"company_name": "Mail Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
        )
        assert setup.status_code == 201


async def promote(email: str, role: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("UPDATE users SET platform_role = :role WHERE email = :email"), {"role": role, "email": email})
        await db.commit()


async def login_headers(client: AsyncClient, email: str) -> dict:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def clear_mail_settings() -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM platform_settings WHERE key = ANY(:keys)"), {"keys": list(MAIL_SETTING_KEYS)})
        await db.commit()


async def cleanup(emails: list[str]) -> None:
    async with SessionLocal() as db:
        for email in emails:
            company_ids = (
                await db.execute(
                    text("SELECT company_id FROM memberships WHERE user_id IN (SELECT id FROM users WHERE email = :email)"),
                    {"email": email},
                )
            ).scalars().all()
            for company_id in company_ids:
                parameters = {"company_id": company_id}
                for statement in [
                    "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                    "DELETE FROM memberships WHERE company_id = :company_id",
                    "DELETE FROM company_currencies WHERE company_id = :company_id",
                    "DELETE FROM stores WHERE company_id = :company_id",
                    "DELETE FROM companies WHERE id = :company_id",
                ]:
                    await db.execute(text(statement), parameters)
            await db.execute(text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_mail_settings_require_admin_and_mask_the_key(monkeypatch) -> None:
    admin = f"mail-admin-{uuid.uuid4().hex[:8]}@example.com"
    calls = {"resend": 0, "smtp": 0}

    def fake_resend(cfg, recipient, subject, text, html, headers, reply_to):
        calls["resend"] += 1

    def fake_smtp(cfg, recipient, subject, text, html, headers, reply_to):
        calls["smtp"] += 1

    import app.services.mail as mail_service

    monkeypatch.setattr(mail_service, "_send_resend", fake_resend)
    monkeypatch.setattr(mail_service, "_send_smtp", fake_smtp)
    try:
        await clear_mail_settings()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin, workspace=True)
            headers = await login_headers(client, admin)

            # A plain user has no platform access at all.
            assert (await client.get("/api/v1/admin/mail-settings", headers=headers)).status_code == 403

            await promote(admin, "admin")
            headers = await login_headers(client, admin)
            read = await client.get("/api/v1/admin/mail-settings", headers=headers)
            assert read.status_code == 200
            body = read.json()
            assert {provider["code"] for provider in body["providers"]} == {"smtp", "resend"}
            assert body["provider"] == "smtp"
            assert body["api_key_set"] is False

            # A plain platform admin may read but not change sending.
            assert (await client.patch("/api/v1/admin/mail-settings", headers=headers, json={"provider": "resend"})).status_code == 403

            await promote(admin, "super_admin")
            headers = await login_headers(client, admin)
            saved = await client.patch(
                "/api/v1/admin/mail-settings",
                headers=headers,
                json={"provider": "resend", "resend_api_key": "re-secret-value", "from_address": "no-reply@chmaba.com", "from_name": "Chmaba"},
            )
            assert saved.status_code == 200
            saved_body = saved.json()
            assert saved_body["provider"] == "resend"
            assert saved_body["api_key_set"] is True
            assert "re-secret-value" not in saved.text
            assert saved_body["api_key_preview"].startswith("re-sec")
            assert saved_body["from_name"] == "Chmaba"

            # Now deliveries route through Resend, not SMTP.
            # (Account setup above already sent a verification email.)
            calls["resend"] = calls["smtp"] = 0
            assert await mail_service.deliver_message(recipient="someone@example.com", subject="Hi", text="Hello") is True
            assert calls["resend"] == 1 and calls["smtp"] == 0

            # The test send surfaces provider errors instead of failing the request.
            def boom(*args, **kwargs):
                raise RuntimeError("Resend rejected the message (401): invalid key")

            monkeypatch.setattr(mail_service, "_send_resend", boom)
            failed = await client.post("/api/v1/admin/mail-settings/test", headers=headers, json={"to": "you@example.com"})
            assert failed.status_code == 200
            assert failed.json()["sent"] is False
            assert failed.json()["provider"] == "resend"
            assert "401" in failed.json()["detail"]

            monkeypatch.setattr(mail_service, "_send_resend", fake_resend)
            ok = await client.post("/api/v1/admin/mail-settings/test", headers=headers, json={"to": "you@example.com"})
            assert ok.status_code == 200 and ok.json()["sent"] is True
    finally:
        await clear_mail_settings()
        await cleanup([admin])


@pytest.mark.asyncio
async def test_switching_back_to_smtp_uses_the_relay(monkeypatch) -> None:
    admin = f"mail-admin-{uuid.uuid4().hex[:8]}@example.com"
    calls = {"resend": 0, "smtp": 0}

    def fake_resend(cfg, recipient, subject, text, html, headers, reply_to):
        calls["resend"] += 1

    def fake_smtp(cfg, recipient, subject, text, html, headers, reply_to):
        calls["smtp"] += 1

    import app.services.mail as mail_service

    monkeypatch.setattr(mail_service, "_send_resend", fake_resend)
    monkeypatch.setattr(mail_service, "_send_smtp", fake_smtp)
    try:
        await clear_mail_settings()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin, workspace=True)
        await promote(admin, "super_admin")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await login_headers(client, admin)
            async with SessionLocal() as db:
                await mail_service.save_mail_settings(db, {"mail_provider": "resend", "resend_api_key": "re-x"})
            calls["resend"] = calls["smtp"] = 0
            assert await mail_service.deliver_message(recipient="a@example.com", subject="s", text="t") is True
            assert calls["resend"] == 1

            await client.patch("/api/v1/admin/mail-settings", headers=headers, json={"provider": "smtp"})
            assert await mail_service.deliver_message(recipient="a@example.com", subject="s", text="t") is True
            assert calls["smtp"] == 1 and calls["resend"] == 1
    finally:
        await clear_mail_settings()
        await cleanup([admin])
