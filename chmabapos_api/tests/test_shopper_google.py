"""Shopper sign-in with Google.

The token verifier is patched rather than mocked over the network: what is worth
testing here is the upsert and linking logic around it, which is where an identity
bug would actually live.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.api import v1 as v1_module
from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import ShopperAccount
from app.security import decode_token


def _claims(email: str, sub: str, *, verified: bool = True) -> dict:
    return {"email": email, "sub": sub, "email_verified": verified, "name": "Sokha Shopper"}


async def _purge(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM shopper_email_codes WHERE shopper_id IN (SELECT id FROM shopper_accounts WHERE email = :e)"), {"e": email})
        await db.execute(text("DELETE FROM shopper_accounts WHERE email = :e"), {"e": email})
        await db.commit()


@pytest.mark.asyncio
async def test_google_sign_in_creates_then_reuses_one_shopper(monkeypatch) -> None:
    email = f"gshopper-{uuid.uuid4().hex[:10]}@example.com"
    sub = f"google-sub-{uuid.uuid4().hex[:10]}"
    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(v1_module, "verify_google_id_token", lambda token, client_id: _claims(email, sub))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post("/api/v1/public/auth/google", json={"id_token": "irrelevant"})
            assert first.status_code == 200, first.text
            body = first.json()
            assert body["shopper"]["email"] == email
            # Google verified the address, so the shopper is verified without a code.
            assert body["shopper"]["is_email_verified"] is True
            # The identity is a shopper, not a staff user.
            assert decode_token(body["access_token"])["type"] == "shopper"

            # Signing in again lands on the same account rather than duplicating it.
            second = await client.post("/api/v1/public/auth/google", json={"id_token": "irrelevant"})
            assert second.status_code == 200, second.text
            assert second.json()["shopper"]["id"] == body["shopper"]["id"]

            async with SessionLocal() as db:
                rows = (
                    await db.execute(select(ShopperAccount).where(ShopperAccount.email == email))
                ).scalars().all()
            assert len(rows) == 1, "a repeat sign-in must not create a second account"
            assert rows[0].google_sub == sub, "the provider id should be linked for future lookups"
    finally:
        await _purge(email)


@pytest.mark.asyncio
async def test_google_sign_in_links_an_existing_code_account(monkeypatch) -> None:
    """Someone who signed in with an emailed code first, then with Google."""
    email = f"gshopper-link-{uuid.uuid4().hex[:10]}@example.com"
    sub = f"google-sub-{uuid.uuid4().hex[:10]}"
    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(v1_module, "verify_google_id_token", lambda token, client_id: _claims(email, sub))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # An account created the other way: unverified, no provider.
            async with SessionLocal() as db:
                db.add(ShopperAccount(email=email))
                await db.commit()

            signed_in = await client.post("/api/v1/public/auth/google", json={"id_token": "irrelevant"})
            assert signed_in.status_code == 200, signed_in.text

            async with SessionLocal() as db:
                rows = (
                    await db.execute(select(ShopperAccount).where(ShopperAccount.email == email))
                ).scalars().all()
            assert len(rows) == 1, "linking must not create a duplicate account"
            assert rows[0].google_sub == sub
            assert rows[0].is_email_verified is True
    finally:
        await _purge(email)


@pytest.mark.asyncio
async def test_google_sign_in_refuses_an_unverified_address(monkeypatch) -> None:
    email = f"gshopper-unverified-{uuid.uuid4().hex[:10]}@example.com"
    sub = f"google-sub-{uuid.uuid4().hex[:10]}"
    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(
        v1_module, "verify_google_id_token", lambda token, client_id: _claims(email, sub, verified=False)
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/public/auth/google", json={"id_token": "irrelevant"})
            assert response.status_code == 401, response.text
    finally:
        # Nothing should have been created for an address Google has not verified.
        async with SessionLocal() as db:
            rows = (
                await db.execute(select(ShopperAccount).where(ShopperAccount.email == email))
            ).scalars().all()
        assert rows == [], "an unverified address must not create an account"
        await _purge(email)
