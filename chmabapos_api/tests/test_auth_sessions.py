"""Server-side session, refresh-rotation and revocation behaviour."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.security import create_token


async def _register_verified(client: AsyncClient, email: str) -> None:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Session Owner", "password": "strong-password"})
    assert register.status_code == 201
    code = register.json()["dev_verification_token"]
    verify = await client.post("/api/v1/auth/verify-email", json={"token": code})
    assert verify.status_code == 200


async def _cleanup(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(
            text("delete from email_verification_tokens where user_id in (select id from users where email = :email)"),
            {"email": email},
        )
        await db.execute(text("delete from users where email = :email"), {"email": email})
        await db.commit()


def _refresh_value(client: AsyncClient) -> str | None:
    return client.cookies.get(settings.session_cookie_name)


@pytest.mark.asyncio
async def test_refresh_rotates_token_and_issues_new_access_token() -> None:
    email = f"sess-rotate-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_verified(client, email)
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password", "remember_me": True})
            assert login.status_code == 200
            first_refresh = _refresh_value(client)
            assert first_refresh

            refreshed = await client.post("/api/v1/auth/refresh")
            assert refreshed.status_code == 200
            assert _refresh_value(client) != first_refresh

            me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"})
            assert me.status_code == 200
            assert me.json()["email"] == email
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_replayed_refresh_token_revokes_session() -> None:
    email = f"sess-replay-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_verified(client, email)
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password", "remember_me": True})
            assert login.status_code == 200
            stolen = _refresh_value(client)
            assert stolen

            rotated = await client.post("/api/v1/auth/refresh")
            assert rotated.status_code == 200
            current = _refresh_value(client)
            rotated_access = rotated.json()["access_token"]
            assert current and current != stolen

            # Replaying the token that pre-dates the rotation is treated as theft.
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={settings.session_cookie_name: stolen},
            ) as replayer:
                assert (await replayer.post("/api/v1/auth/refresh")).status_code == 401

            # The whole session is revoked: the rotated token no longer works, and
            # neither does the access token minted alongside it.
            assert (await client.post("/api/v1/auth/refresh")).status_code == 401
            me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {rotated_access}"})
            assert me.status_code == 401
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_logout_revokes_the_access_token() -> None:
    email = f"sess-logout-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_verified(client, email)
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password", "remember_me": True})
            assert login.status_code == 200
            token = login.json()["access_token"]
            assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 200

            assert (await client.post("/api/v1/auth/logout")).status_code == 204
            assert not _refresh_value(client)

            # Revocation is immediate, not "when the token expires".
            assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401
            assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    finally:
        await _cleanup(email)


@pytest.mark.asyncio
async def test_token_without_session_is_rejected() -> None:
    email = f"sess-legacy-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_verified(client, email)
        async with SessionLocal() as db:
            user_id = (await db.execute(text("select id from users where email = :email"), {"email": email})).scalar_one()
        # A token minted before server-side sessions (no ``sid``) must not work.
        legacy = create_token(user_id)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {legacy}"})
            assert me.status_code == 401
    finally:
        await _cleanup(email)
