"""Shopper sign-in with Telegram.

The signature is the entire authentication: the payload arrives from the browser,
so without a correct HMAC anyone could POST any Telegram user id and be signed in
as that person. These tests therefore spend most of their effort on the cases
where the signature must NOT be accepted.
"""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import ShopperAccount
from app.security import decode_token

BOT_TOKEN = "test-bot-token"


def _signed(fields: dict) -> dict:
    """A payload signed the way Telegram signs it."""
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hashlib.sha256(BOT_TOKEN.encode("utf-8")).digest()
    digest = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return {**fields, "hash": digest}


async def _purge(telegram_id: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM shopper_accounts WHERE telegram_id = :t"), {"t": telegram_id})
        await db.commit()


def _fields(telegram_id: str, *, auth_date: int | None = None) -> dict:
    return {
        "id": telegram_id,
        "first_name": "Sokha",
        "last_name": "Shopper",
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
    }


@pytest.mark.asyncio
async def test_telegram_sign_in_creates_then_reuses_one_shopper(monkeypatch) -> None:
    telegram_id = str(uuid.uuid4().int)[:10]
    monkeypatch.setattr(settings, "telegram_bot_token", BOT_TOKEN)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post("/api/v1/public/auth/telegram", json=_signed(_fields(telegram_id)))
            assert first.status_code == 200, first.text
            body = first.json()
            # No address, and no placeholder for one.
            assert body["shopper"]["email"] is None
            assert body["shopper"]["full_name"] == "Sokha Shopper"
            assert decode_token(body["access_token"])["type"] == "shopper"

            second = await client.post("/api/v1/public/auth/telegram", json=_signed(_fields(telegram_id)))
            assert second.status_code == 200, second.text
            assert second.json()["shopper"]["id"] == body["shopper"]["id"]

            async with SessionLocal() as db:
                rows = (
                    await db.execute(select(ShopperAccount).where(ShopperAccount.telegram_id == telegram_id))
                ).scalars().all()
            assert len(rows) == 1, "a repeat sign-in must not create a second account"
            assert rows[0].email is None
    finally:
        await _purge(telegram_id)


@pytest.mark.asyncio
async def test_telegram_sign_in_rejects_a_tampered_payload(monkeypatch) -> None:
    """The signature covers the fields, so swapping the id must not be accepted."""
    monkeypatch.setattr(settings, "telegram_bot_token", BOT_TOKEN)
    victim_id = str(uuid.uuid4().int)[:10]
    attacker_id = str(uuid.uuid4().int)[:10]
    signed = _signed(_fields(victim_id))
    tampered = {**signed, "id": attacker_id}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/public/auth/telegram", json=tampered)
            assert response.status_code == 401, response.text
    finally:
        await _purge(victim_id)
        await _purge(attacker_id)


@pytest.mark.asyncio
async def test_telegram_sign_in_rejects_a_stale_payload(monkeypatch) -> None:
    """A valid signature only proves provenance, not freshness."""
    telegram_id = str(uuid.uuid4().int)[:10]
    monkeypatch.setattr(settings, "telegram_bot_token", BOT_TOKEN)
    stale = _signed(_fields(telegram_id, auth_date=int(time.time()) - 60 * 60 * 72))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/public/auth/telegram", json=stale)
            assert response.status_code == 401, response.text
    finally:
        await _purge(telegram_id)


@pytest.mark.asyncio
async def test_telegram_sign_in_is_unavailable_when_unconfigured(monkeypatch) -> None:
    telegram_id = str(uuid.uuid4().int)[:10]
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/public/auth/telegram", json=_signed(_fields(telegram_id)))
        assert response.status_code == 503, response.text
