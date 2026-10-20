"""Dual currency only: a base plus one alternate, enforced by the API.

The settings UI can hide the third option, but the API is what a client actually
calls. A workspace with three currencies would multiply the tender, change,
refund and rounding paths for a market that uses two.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_lifecycle import cleanup_company, register_and_setup


@pytest.mark.asyncio
async def test_a_third_currency_is_refused() -> None:
    email: str | None = None
    company_id: str | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ctx = await register_and_setup(client, "Dual Co", "Main", plan="pro", email_prefix="dual-cap")
            email, company_id = ctx["email"], ctx["company_id"]

            two = await client.put(
                "/api/v1/settings/currencies", headers=ctx["headers"], json={"primary_code": "USD", "enabled_codes": ["USD", "KHR"]}
            )
            assert two.status_code == 200, two.text
            assert {row["currency"]["code"] for row in two.json() if row["is_enabled"]} == {"USD", "KHR"}

            three = await client.put(
                "/api/v1/settings/currencies",
                headers=ctx["headers"],
                json={"primary_code": "USD", "enabled_codes": ["USD", "KHR", "THB"]},
            )
            assert three.status_code == 422, three.text
            assert "two currencies" in three.text, three.text
    finally:
        await cleanup_company(company_id, [email] if email else [])
