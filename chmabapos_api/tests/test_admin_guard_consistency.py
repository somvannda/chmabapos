"""Platform-admin guard consistency.

ChmabaPay credentials and destructive mailing operations are as sensitive as the
mail/AI secrets, which already require `super_admin`. This pins that a plain
platform `admin` cannot write/reveal gateway secrets or delete templates, and
that the final active `super_admin` cannot lock the platform out.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app

CHAMABAPAY_KEYS = (
    "chamabapay_mode",
    "chamabapay_api_url",
    "chamabapay_api_key",
    "chamabapay_webhook_secret",
    "chamabapay_platform_store_id",
)


async def register_verified(client: AsyncClient, email: str) -> None:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Guard Tester", "password": "strong-password"})
    assert register.status_code == 201, register.text
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})


async def promote(email: str, role: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("UPDATE users SET platform_role = :role WHERE email = :email"), {"role": role, "email": email})
        await db.commit()


async def user_id(email: str) -> str:
    async with SessionLocal() as db:
        return str((await db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email})).scalar_one())


async def login_headers(client: AsyncClient, email: str) -> dict:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def cleanup(emails: list[str]) -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM platform_settings WHERE key = ANY(:keys)"), {"keys": list(CHAMABAPAY_KEYS)})
        for email in emails:
            await db.execute(text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_gateway_and_template_writes_require_super_admin() -> None:
    admin = f"guard-admin-{uuid.uuid4().hex[:8]}@example.com"
    superadmin = f"guard-super-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin)
            await register_verified(client, superadmin)
            await promote(admin, "admin")
            await promote(superadmin, "super_admin")
            admin_headers = await login_headers(client, admin)
            super_headers = await login_headers(client, superadmin)

            # A plain admin cannot change or read back the gateway secret.
            assert (await client.patch("/api/v1/admin/chamabapay-settings", headers=admin_headers, json={"mode": "mock"})).status_code == 403
            assert (await client.post("/api/v1/admin/chamabapay-settings/reveal", headers=admin_headers, json={"field": "api_key"})).status_code == 403

            # A super admin can.
            assert (await client.patch("/api/v1/admin/chamabapay-settings", headers=super_headers, json={"mode": "mock"})).status_code == 200
            assert (await client.post("/api/v1/admin/chamabapay-settings/reveal", headers=super_headers, json={"field": "api_key"})).status_code == 200

            # Template creation stays open to admins, deletion does not.
            created = await client.post("/api/v1/admin/mailing/templates", headers=admin_headers, json={"name": f"Guard Template {uuid.uuid4().hex[:6]}", "subject": "Hi", "body_html": "<p>hi</p>"})
            assert created.status_code == 201, created.text
            template_id = created.json()["id"]
            assert (await client.delete(f"/api/v1/admin/mailing/templates/{template_id}", headers=admin_headers)).status_code == 403
            assert (await client.delete(f"/api/v1/admin/mailing/templates/{template_id}", headers=super_headers)).status_code == 204
    finally:
        await cleanup([admin, superadmin])


@pytest.mark.asyncio
async def test_last_super_admin_cannot_demote_themselves() -> None:
    target = f"guard-last-{uuid.uuid4().hex[:8]}@example.com"
    demoted: list[str] = []
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, target)
        await promote(target, "super_admin")

        # Make the target the only active super admin for a deterministic check.
        async with SessionLocal() as db:
            others = (await db.execute(text("SELECT email FROM users WHERE platform_role = 'super_admin' AND is_active AND email != :email"), {"email": target})).scalars().all()
            for email in others:
                await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": email})
                demoted.append(email)
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await login_headers(client, target)
            target_id = await user_id(target)
            blocked = await client.patch(f"/api/v1/admin/users/{target_id}", headers=headers, json={"platform_role": "admin"})
            assert blocked.status_code == 400, blocked.text
    finally:
        async with SessionLocal() as db:
            for email in demoted:
                await db.execute(text("UPDATE users SET platform_role = 'super_admin' WHERE email = :email"), {"email": email})
            await db.commit()
        await cleanup([target])
