"""Cloudflare Turnstile verification on the public auth endpoints.

The check is a no-op when unconfigured (so dev/tests keep working) and fails
closed when configured. These tests exercise both paths without real network.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.services.turnstile as turnstile
from app.api.v1 import enforce_turnstile
from app.config import settings


@pytest.mark.asyncio
async def test_verify_skips_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "turnstile_secret_key", None)
    assert await turnstile.verify_turnstile(None) is True


@pytest.mark.asyncio
async def test_verify_rejects_missing_token_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "turnstile_secret_key", "secret")
    assert await turnstile.verify_turnstile(None) is False


@pytest.mark.asyncio
async def test_verify_posts_token_and_ip_to_siteverify(monkeypatch) -> None:
    monkeypatch.setattr(settings, "turnstile_secret_key", "secret")
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"success": True}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> bool:
            return False

        async def post(self, url, data=None):
            captured["url"] = url
            captured["data"] = data
            return FakeResponse()

    monkeypatch.setattr(turnstile.httpx, "AsyncClient", FakeClient)

    assert await turnstile.verify_turnstile("tok", remote_ip="1.2.3.4") is True
    assert captured["url"] == settings.turnstile_verify_url
    assert captured["data"]["secret"] == "secret"
    assert captured["data"]["response"] == "tok"
    assert captured["data"]["remoteip"] == "1.2.3.4"


@pytest.mark.asyncio
async def test_verify_fails_closed_on_network_error(monkeypatch) -> None:
    monkeypatch.setattr(settings, "turnstile_secret_key", "secret")

    class BoomClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> bool:
            return False

        async def post(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(turnstile.httpx, "AsyncClient", BoomClient)
    assert await turnstile.verify_turnstile("tok") is False


@pytest.mark.asyncio
async def test_enforce_turnstile_rejects_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "turnstile_secret_key", "secret")

    async def fake_verify(token, *, remote_ip=None):
        return False

    monkeypatch.setattr("app.api.v1.verify_turnstile", fake_verify)
    request = SimpleNamespace(client=SimpleNamespace(host="1.2.3.4"))
    with pytest.raises(HTTPException) as exc:
        await enforce_turnstile("bad-token", request)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_enforce_turnstile_is_noop_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "turnstile_secret_key", None)

    async def fake_verify(token, *, remote_ip=None):
        return False

    monkeypatch.setattr("app.api.v1.verify_turnstile", fake_verify)
    request = SimpleNamespace(client=None)
    # Must not raise even though verification would fail.
    await enforce_turnstile(None, request)


@pytest.mark.asyncio
async def test_register_rejects_bot_when_configured(monkeypatch) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    monkeypatch.setattr(settings, "turnstile_secret_key", "secret")

    async def fake_verify(token, *, remote_ip=None):
        return False

    monkeypatch.setattr("app.api.v1.verify_turnstile", fake_verify)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "bot@example.com", "full_name": "Bot Bot", "password": "strong-password"},
        )
    assert response.status_code == 400
    assert "human" in response.json()["detail"].lower()
