"""Rate limiting on the unauthenticated public surface.

Enforced by middleware over the whole `/api/v1/public/` prefix, so these tests
drive real requests rather than calling a helper - the thing worth proving is that
the limit is actually wired in.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services import support
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_public_order_submission_is_rate_limited(monkeypatch) -> None:
    support._rate_windows.clear()
    monkeypatch.setattr(settings, "public_order_rate_limit_per_minute", 1)
    monkeypatch.setattr(settings, "public_read_rate_limit_per_minute", 50)

    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Limit Co {suffix}", f"Till {suffix}", email_prefix="rate-limit", plan="starter")
            email, company_id = ctx["email"], ctx["company_id"]
            category_id = (await client.get("/api/v1/categories", headers=ctx["headers"])).json()[0]["id"]
            product = (
                await client.post(
                    "/api/v1/products",
                    headers=ctx["store_headers"],
                    json={
                        "name": "Limited Latte",
                        "sku": f"RL-{suffix}",
                        "price": "3.00",
                        "category_id": category_id,
                        "opening_stock": 20,
                    },
                )
            ).json()
            enabled = await client.patch(
                f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True}
            )
            token = enabled.json()["token"]

            payload = {"items": [{"product_id": product["id"], "quantity": 1}]}
            first = await client.post(f"/api/v1/public/order/{token}", json=payload)
            assert first.status_code == 201, first.text

            # The limit is one per minute, so the next submission is refused.
            second = await client.post(f"/api/v1/public/order/{token}", json=payload)
            assert second.status_code == 429, second.text
            assert "Too many requests" in second.json()["detail"]

            # Reads have their own budget, so browsing is not broken by an order
            # burst - which is what would happen if both shared one counter.
            menu = await client.get(f"/api/v1/public/order/{token}")
            assert menu.status_code == 200, menu.text
    finally:
        support._rate_windows.clear()
        if company_id:
            await cleanup_company(company_id, [email] if email else [])


@pytest.mark.asyncio
async def test_public_reads_have_their_own_budget(monkeypatch) -> None:
    support._rate_windows.clear()
    monkeypatch.setattr(settings, "public_read_rate_limit_per_minute", 1)
    monkeypatch.setattr(settings, "public_order_rate_limit_per_minute", 50)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.get("/api/v1/public/stores")
            assert first.status_code == 200, first.text
            second = await client.get("/api/v1/public/stores")
            assert second.status_code == 429, second.text
    finally:
        support._rate_windows.clear()


@pytest.mark.asyncio
async def test_a_zero_limit_disables_the_check(monkeypatch) -> None:
    """The escape hatch the suite relies on must actually work."""
    support._rate_windows.clear()
    monkeypatch.setattr(settings, "public_read_rate_limit_per_minute", 0)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(5):
                response = await client.get("/api/v1/public/stores")
                assert response.status_code == 200, response.text
    finally:
        support._rate_windows.clear()
