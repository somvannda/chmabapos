"""Reproduction tests for the auth-abuse hardening (docs/auth-abuse-hardening.md).

These cover the pieces that made the November 2026 probe sign-ups possible:
open registration on reserved/disposable domains, no throttling of verification
or sign-in, and a suspended account still being able to start a session.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, update

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import User
from app.services import email_policy, support as support_service
from app.services.client_ip import client_ip


async def _register_and_verify(client: AsyncClient, email: str, password: str = "strong-password") -> None:
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Hardening Test", "password": password},
    )
    assert registered.status_code == 201, registered.text
    code = registered.json()["dev_verification_token"]
    verified = await client.post("/api/v1/auth/verify-email", json={"token": code})
    assert verified.status_code == 200, verified.text


async def _delete_user(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(delete(User).where(User.email == email))
        await db.commit()


def test_reserved_and_disposable_domains_are_blocked_in_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")

    assert email_policy.blocked_reason("probe@example.com")
    assert email_policy.blocked_reason("probe@sub.mailinator.com")
    assert email_policy.blocked_reason("probe@euploading.com")
    assert email_policy.blocked_reason("owner@chmaba.com") is None


def test_reserved_domains_stay_usable_outside_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "test")

    assert email_policy.blocked_reason("probe@example.com") is None


@pytest.mark.asyncio
async def test_register_rejects_reserved_domain_in_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    email = f"probe-{uuid.uuid4().hex[:8]}@example.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "full_name": "Probe User", "password": "strong-password"},
        )

    assert response.status_code == 400
    assert "permanent email" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_refuses_a_suspended_account() -> None:
    email = f"suspended-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_and_verify(client, email)
            async with SessionLocal() as db:
                await db.execute(update(User).where(User.email == email).values(is_active=False))
                await db.commit()

            login = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "strong-password"},
            )

        assert login.status_code == 403
        assert "suspended" in login.json()["detail"].lower()
    finally:
        await _delete_user(email)


@pytest.mark.asyncio
async def test_login_locks_after_repeated_failures(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_login_failure_limit", 3)
    monkeypatch.setattr(settings, "auth_login_failure_window_minutes", 15)
    email = f"lockout-{uuid.uuid4().hex[:8]}@example.com"
    support_service.clear_rate_limit(f"login-attempt:{email}")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_and_verify(client, email)
            for _ in range(3):
                failed = await client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": "wrong-password"},
                )
                assert failed.status_code == 401
            locked = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "strong-password"},
            )

        assert locked.status_code == 429
    finally:
        support_service.clear_rate_limit(f"login-attempt:{email}")
        await _delete_user(email)


@pytest.mark.asyncio
async def test_register_is_rate_limited_per_client(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_register_rate_limit_per_hour", 1)
    support_service._rate_windows.clear()
    first = f"limit-a-{uuid.uuid4().hex[:8]}@example.com"
    second = f"limit-b-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            accepted = await client.post(
                "/api/v1/auth/register",
                json={"email": first, "full_name": "Limit A", "password": "strong-password"},
            )
            rejected = await client.post(
                "/api/v1/auth/register",
                json={"email": second, "full_name": "Limit B", "password": "strong-password"},
            )

        assert accepted.status_code == 201
        assert rejected.status_code == 429
    finally:
        await _delete_user(first)
        await _delete_user(second)


def test_client_ip_prefers_proxy_headers_and_ignores_client_supplied_prefix() -> None:
    peer = SimpleNamespace(client=SimpleNamespace(host="172.18.0.5"))

    real = SimpleNamespace(headers={"x-real-ip": "203.0.113.9"}, client=peer.client)
    assert client_ip(real) == "203.0.113.9"

    cloudflare = SimpleNamespace(headers={"cf-connecting-ip": "198.51.100.7"}, client=peer.client)
    assert client_ip(cloudflare) == "198.51.100.7"

    forwarded = SimpleNamespace(
        headers={"x-forwarded-for": "1.2.3.4, 198.51.100.7"},
        client=peer.client,
    )
    assert client_ip(forwarded) == "198.51.100.7"

    invalid = SimpleNamespace(headers={"x-real-ip": "not-an-ip"}, client=peer.client)
    assert client_ip(invalid) == "172.18.0.5"

    plain = SimpleNamespace(headers={}, client=peer.client)
    assert client_ip(plain) == "172.18.0.5"
