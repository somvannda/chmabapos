"""Configurable sign-in session length.

Covers the resolver (platform default -> company override -> platform cap) and
the owner-facing settings endpoints, plus the platform policy round-trip.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import Company, Membership, User
from app.services.session_policy import (
    load_platform_session_policy,
    resolve_session_ttl_minutes,
    save_platform_session_policy,
)


_POLICY_KEYS = ("session_default_ttl_minutes", "session_max_ttl_minutes")


async def _snapshot_platform_policy() -> dict[str, str | None]:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT key, value FROM platform_settings "
                    "WHERE key IN ('session_default_ttl_minutes', 'session_max_ttl_minutes')"
                )
            )
        ).all()
        return {row.key: row.value for row in rows}


async def _restore_platform_policy(original: dict[str, str | None]) -> None:
    async with SessionLocal() as db:
        for key in _POLICY_KEYS:
            if key in original:
                await db.execute(
                    text("UPDATE platform_settings SET value = :value WHERE key = :key"),
                    {"value": original[key], "key": key},
                )
            else:
                await db.execute(text("DELETE FROM platform_settings WHERE key = :key"), {"key": key})
        await db.commit()


async def _cleanup_workspace(email: str, company_id: str | None) -> None:
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
                "DELETE FROM subscription_capacity_actions WHERE company_id = :company_id",
                "DELETE FROM billing_refunds WHERE company_id = :company_id",
                "DELETE FROM billing_receipts WHERE company_id = :company_id",
                "DELETE FROM billing_payments USING subscriptions WHERE billing_payments.subscription_id = subscriptions.id AND subscriptions.company_id = :company_id",
                "DELETE FROM subscriptions WHERE company_id = :company_id",
                "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                "DELETE FROM memberships WHERE company_id = :company_id",
                "DELETE FROM invitations WHERE company_id = :company_id",
                "DELETE FROM company_currencies WHERE company_id = :company_id",
                "DELETE FROM categories WHERE company_id = :company_id",
                "DELETE FROM stores WHERE company_id = :company_id",
                "DELETE FROM companies WHERE id = :company_id",
            ]
            for statement in statements:
                await db.execute(text(statement), parameters)
        await db.execute(
            text("DELETE FROM auth_sessions WHERE user_id IN (SELECT id FROM users WHERE email = :email)"),
            {"email": email},
        )
        await db.execute(
            text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"),
            {"email": email},
        )
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_resolver_uses_default_override_and_cap() -> None:
    email = f"sess-resolve-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with SessionLocal() as db:
            user = User(email=email, full_name="Resolve Owner", password_hash="x", is_email_verified=True)
            db.add(user)
            await db.flush()

            # No company yet -> the platform default.
            assert await resolve_session_ttl_minutes(db, user, remember=False) == settings.jwt_session_ttl_minutes
            # "Remember me" opts into the longer remembered lifetime.
            assert await resolve_session_ttl_minutes(db, user, remember=True) == min(
                settings.jwt_remember_ttl_minutes, settings.jwt_max_session_ttl_minutes
            )

            company = Company(name="Resolve Co", settings={"session_ttl_minutes": 90})
            db.add(company)
            await db.flush()
            db.add(Membership(company_id=company.id, user_id=user.id, role="owner", status="active"))
            await db.flush()

            # The company override wins for normal sign-ins.
            assert await resolve_session_ttl_minutes(db, user, remember=False) == 90

            # A value above the platform maximum is clamped.
            company.settings = {"session_ttl_minutes": settings.jwt_max_session_ttl_minutes + 5000}
            await db.flush()
            assert await resolve_session_ttl_minutes(db, user, remember=False) == settings.jwt_max_session_ttl_minutes

            company_id = company.id
            await db.rollback()
    finally:
        async with SessionLocal() as db:
            if company_id:
                await db.execute(text("DELETE FROM memberships WHERE company_id = :company_id"), {"company_id": company_id})
                await db.execute(text("DELETE FROM companies WHERE id = :company_id"), {"company_id": company_id})
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
            await db.commit()


@pytest.mark.asyncio
async def test_platform_session_policy_roundtrip_and_clamp() -> None:
    original = await _snapshot_platform_policy()
    try:
        async with SessionLocal() as db:
            await save_platform_session_policy(db, default_minutes=240, max_minutes=1440)
            await db.commit()
            assert await load_platform_session_policy(db) == (240, 1440)

        async with SessionLocal() as db:
            # A default above the maximum clamps down to the maximum.
            await save_platform_session_policy(db, default_minutes=999999)
            await db.commit()
            default, maximum = await load_platform_session_policy(db)
            assert maximum == 1440
            assert default == 1440
    finally:
        await _restore_platform_policy(original)


@pytest.mark.asyncio
async def test_company_session_settings_endpoints() -> None:
    email = f"sess-company-{uuid.uuid4().hex[:10]}@example.com"
    company_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "full_name": "Company Session", "password": "strong-password"},
            )
            assert register.status_code == 201
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            setup = await client.post(
                "/api/v1/workspaces/setup",
                headers=headers,
                json={"company_name": "Session Store", "store_name": "Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
            )
            assert setup.status_code == 201
            company_id = setup.json()["company"]["id"]

            policy = await client.get("/api/v1/settings/session", headers=headers)
            assert policy.status_code == 200
            body = policy.json()
            assert body["company_ttl_minutes"] is None
            assert body["default_ttl_minutes"] == settings.jwt_session_ttl_minutes
            assert body["max_ttl_minutes"] == settings.jwt_max_session_ttl_minutes

            updated = await client.put("/api/v1/settings/session", headers=headers, json={"ttl_minutes": 120})
            assert updated.status_code == 200
            assert updated.json()["company_ttl_minutes"] == 120

            # A fresh sign-in for a member of that company now lasts two hours.
            fresh = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            assert fresh.status_code == 200
            async with SessionLocal() as db:
                row = (
                    await db.execute(
                        text(
                            "SELECT expires_at, last_used_at FROM auth_sessions "
                            "WHERE user_id = (SELECT id FROM users WHERE email = :email) "
                            "ORDER BY last_used_at DESC LIMIT 1"
                        ),
                        {"email": email},
                    )
                ).one()
            lifetime_minutes = (row.expires_at - row.last_used_at).total_seconds() / 60
            assert 118 <= lifetime_minutes <= 122

            # Over the platform maximum is rejected.
            too_long = await client.put(
                "/api/v1/settings/session",
                headers=headers,
                json={"ttl_minutes": settings.jwt_max_session_ttl_minutes + 1},
            )
            assert too_long.status_code == 400

            # Clearing the override reverts to the platform default.
            cleared = await client.put("/api/v1/settings/session", headers=headers, json={"ttl_minutes": None})
            assert cleared.status_code == 200
            assert cleared.json()["company_ttl_minutes"] is None
    finally:
        await _cleanup_workspace(email, company_id)
