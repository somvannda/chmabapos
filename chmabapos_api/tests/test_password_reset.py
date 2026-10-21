"""A password reset link is single-use and dies with the password it set."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import PasswordResetToken, User, utcnow
from app.security import hash_opaque_token

PASSWORD = "strong-password"
NEW_PASSWORD = "new-strong-password"


async def _register_verified(client: AsyncClient, email: str) -> None:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Reset Owner", "password": PASSWORD})
    assert register.status_code == 201
    verify = await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    assert verify.status_code == 200


async def _issue_token(email: str, token: str, *, minutes: int = 30) -> None:
    async with SessionLocal() as db:
        user_id = (await db.execute(select(User.id).where(User.email == email))).scalar_one()
        db.add(
            PasswordResetToken(
                user_id=user_id,
                token_hash=hash_opaque_token(token),
                expires_at=utcnow() + timedelta(minutes=minutes),
            )
        )
        await db.commit()


async def _cleanup(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(
            text("delete from email_verification_tokens where user_id in (select id from users where email = :email)"),
            {"email": email},
        )
        await db.execute(
            text("delete from password_reset_tokens where user_id in (select id from users where email = :email)"),
            {"email": email},
        )
        await db.execute(text("delete from users where email = :email"), {"email": email})
        await db.commit()


@pytest.mark.asyncio
async def test_reset_link_is_single_use_and_validated_before_the_form() -> None:
    email = f"reset-once-{uuid.uuid4().hex[:10]}@example.com"
    token = f"reset-token-{uuid.uuid4().hex}{uuid.uuid4().hex}"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_verified(client, email)
            await _issue_token(email, token)

            # A fresh link is reported usable by the page-load check.
            valid = await client.post("/api/v1/auth/reset-password/validate", json={"token": token})
            assert valid.status_code == 200
            assert valid.json() == {"valid": True}

            reset = await client.post("/api/v1/auth/reset-password", json={"token": token, "password": NEW_PASSWORD})
            assert reset.status_code == 200

            # Reopening the email link now says so immediately, and a forced
            # submission is rejected too.
            reused = await client.post("/api/v1/auth/reset-password/validate", json={"token": token})
            assert reused.status_code == 400
            assert reused.json()["detail"] == "Password reset link is invalid or has expired"
            assert (await client.post("/api/v1/auth/reset-password", json={"token": token, "password": PASSWORD})).status_code == 400

            assert (await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})).status_code == 401
            assert (await client.post("/api/v1/auth/login", json={"email": email, "password": NEW_PASSWORD})).status_code == 200
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_expired_link_is_rejected() -> None:
    email = f"reset-expired-{uuid.uuid4().hex[:10]}@example.com"
    token = f"reset-token-{uuid.uuid4().hex}{uuid.uuid4().hex}"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_verified(client, email)
            await _issue_token(email, token, minutes=-1)

            assert (await client.post("/api/v1/auth/reset-password/validate", json={"token": token})).status_code == 400
            assert (await client.post("/api/v1/auth/reset-password", json={"token": token, "password": NEW_PASSWORD})).status_code == 400
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_requesting_a_new_link_retires_the_previous_one() -> None:
    email = f"reset-newest-{uuid.uuid4().hex[:10]}@example.com"
    old_token = f"reset-token-{uuid.uuid4().hex}{uuid.uuid4().hex}"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_verified(client, email)
            await _issue_token(email, old_token)

            # Asking for another link must silence the one already in the inbox.
            requested = await client.post("/api/v1/auth/request-password-reset", json={"email": email})
            assert requested.status_code == 200

            retired = await client.post("/api/v1/auth/reset-password/validate", json={"token": old_token})
            assert retired.status_code == 400
            assert (await client.post("/api/v1/auth/reset-password", json={"token": old_token, "password": NEW_PASSWORD})).status_code == 400
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_reset_revokes_every_existing_session() -> None:
    email = f"reset-sessions-{uuid.uuid4().hex[:10]}@example.com"
    token = f"reset-token-{uuid.uuid4().hex}{uuid.uuid4().hex}"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as device:
            await _register_verified(device, email)
            login = await device.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD, "remember_me": True})
            assert login.status_code == 200
            access_token = login.json()["access_token"]
            assert device.cookies.get(settings.session_cookie_name)
            assert (await device.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})).status_code == 200

            await _issue_token(email, token)
            reset = await device.post("/api/v1/auth/reset-password", json={"token": token, "password": NEW_PASSWORD})
            assert reset.status_code == 200

            # The point of a reset is to evict whoever already had the account.
            assert (await device.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})).status_code == 401
            assert (await device.post("/api/v1/auth/refresh")).status_code == 401
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_change_password_retires_outstanding_reset_links() -> None:
    email = f"reset-change-{uuid.uuid4().hex[:10]}@example.com"
    token = f"reset-token-{uuid.uuid4().hex}{uuid.uuid4().hex}"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_verified(client, email)
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD, "remember_me": True})
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            await _issue_token(email, token)

            changed = await client.post(
                "/api/v1/auth/change-password",
                headers=headers,
                json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            )
            assert changed.status_code == 200

            assert (await client.post("/api/v1/auth/reset-password/validate", json={"token": token})).status_code == 400
    finally:
        await _cleanup(email)
