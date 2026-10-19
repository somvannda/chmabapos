"""Shopper sessions can be revoked.

Signing in starts a session and the access token names it, so signing out kills
the token at once instead of leaving a copied one usable until it expires.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import ShopperAccount, ShopperEmailCode, ShopperSession
from app.security import hash_opaque_token
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _make_shopper_with_code(email: str, code: str) -> str:
    async with SessionLocal() as db:
        shopper = ShopperAccount(email=email)
        db.add(shopper)
        await db.flush()
        db.add(
            ShopperEmailCode(
                shopper_id=shopper.id,
                token_hash=hash_opaque_token(code),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            )
        )
        await db.commit()
        return str(shopper.id)


async def _purge_shopper(shopper_id: str | None) -> None:
    if not shopper_id:
        return
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM shopper_accounts WHERE id = :i"), {"i": shopper_id})
        await db.commit()


@pytest.mark.asyncio
async def test_signing_in_starts_a_session_and_logout_revokes_the_token() -> None:
    shopper_id: str | None = None
    buyer = f"session-shopper-{uuid.uuid4().hex[:10]}@example.com"
    code = "246810"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            shopper_id = await _make_shopper_with_code(buyer, code)
            verified = await client.post("/api/v1/public/auth/verify", json={"email": buyer, "code": code})
            assert verified.status_code == 200, verified.text
            token = verified.json()["access_token"]
            auth = {"Authorization": f"Bearer {token}"}

            # 1. Signing in created a session, and the token works.
            me = await client.get("/api/v1/public/auth/me", headers=auth)
            assert me.status_code == 200, me.text

            async with SessionLocal() as db:
                live = (
                    await db.execute(select(ShopperSession).where(ShopperSession.shopper_id == uuid.UUID(shopper_id)))
                ).scalars().all()
                assert len(live) == 1, "one session per sign-in"
                assert live[0].revoked_at is None

            # 2. Signing out revokes it, and the same token is refused at once.
            out = await client.post("/api/v1/public/auth/logout", headers=auth)
            assert out.status_code == 204, out.text
            assert (await client.get("/api/v1/public/auth/me", headers=auth)).status_code == 401

            # 3. Signing out again is harmless - it must never be able to fail.
            assert (await client.post("/api/v1/public/auth/logout", headers=auth)).status_code == 204
    finally:
        await _purge_shopper(shopper_id)


@pytest.mark.asyncio
async def test_a_revoked_session_is_refused_even_with_a_valid_token() -> None:
    """The point of the session: revoking it kills a token that is otherwise fine."""
    shopper_id: str | None = None
    buyer = f"revoked-shopper-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            shopper_id = await _make_shopper_with_code(buyer, "135791")
            verified = await client.post("/api/v1/public/auth/verify", json={"email": buyer, "code": "135791"})
            token = verified.json()["access_token"]
            auth = {"Authorization": f"Bearer {token}"}
            assert (await client.get("/api/v1/public/auth/orders", headers=auth)).status_code == 200

            # Revoked out of band, as an account-deletion or "sign out everywhere" would.
            async with SessionLocal() as db:
                session = (
                    await db.execute(select(ShopperSession).where(ShopperSession.shopper_id == uuid.UUID(shopper_id)))
                ).scalars().first()
                session.revoked_at = datetime.now(timezone.utc)
                await db.commit()

            assert (await client.get("/api/v1/public/auth/orders", headers=auth)).status_code == 401
            assert (await client.get("/api/v1/public/auth/me", headers=auth)).status_code == 401
    finally:
        await _purge_shopper(shopper_id)


@pytest.mark.asyncio
async def test_a_server_minted_token_without_a_session_still_works() -> None:
    """Attribution and chat mint tokens server-side; those must keep working.

    The session check applies to tokens that name one, so requiring a session for
    every token would break the paths that legitimately have none.
    """
    from app.security import create_token

    shopper_id: str | None = None
    try:
        async with SessionLocal() as db:
            shopper = ShopperAccount(email=f"nosession-{uuid.uuid4().hex[:10]}@example.com")
            db.add(shopper)
            await db.commit()
            shopper_id = str(shopper.id)
        token = create_token(uuid.UUID(shopper_id), token_type="shopper")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            me = await client.get("/api/v1/public/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me.status_code == 200, me.text
    finally:
        await _purge_shopper(shopper_id)
